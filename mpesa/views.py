import json

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from .models import Transaction
from requests.auth import HTTPBasicAuth
from django.core.mail import send_mail
import datetime
import base64
from .utility import CALLBACK_URL, MPESA_API_URL, MPESA_PASSKEY, MPESA_CONSUMER_SECRET, MPESA_CONSUMER_KEY, MPESA_SHORTCODE, AUTH_URL


def index(request):
    return render(request, "payment.html")

@csrf_exempt
def stk_push(request):
    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        amount = request.POST.get("amount", "").strip()

        # 1️⃣ Get OAuth token
        auth_url = AUTH_URL
        response = requests.get(auth_url, auth=HTTPBasicAuth(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET))
        access_token = response.json().get("access_token")

        if not access_token:
            return JsonResponse({"status": "error", "message": "Failed to get access token"}, status=500)

        # 2️⃣ Build password and timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        data_to_encode = MPESA_SHORTCODE + MPESA_PASSKEY + timestamp
        password = base64.b64encode(data_to_encode.encode()).decode("utf-8")

        transaction = Transaction.objects.create(
            phone = phone,
            amount = amount,

        )

        # 3️⃣ Build STK Push payload
        payload = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,               # Customer phone
            "PartyB": MPESA_SHORTCODE,     # Paybill
            "PhoneNumber": phone,
            "CallBackURL": f"{CALLBACK_URL}/callback/",  # Replace with your endpoint
            "AccountReference": f"Transaction {transaction.id}",
            "TransactionDesc": "Payment for services"
        }

        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(MPESA_API_URL, json=payload, headers=headers)
        print("response" ,response)
        response_data = response.json()

        print(response_data)

        transaction_id = response_data.get('CheckoutRequestID', None)
        transaction.transaction_id = transaction_id
        transaction.description = response_data.get('ResponseDescription', "No Description")
        transaction.save()
# JsonResponse(stk_response.json())
        return redirect('waiting_page', transaction_id=transaction.id)

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)

def waiting_page(request, transaction_id):
    transaction = Transaction.objects.get(id=transaction_id)
    return render(request, 'waiting.html',{'transaction_id': transaction_id})


@csrf_exempt
def callback(request):
    if request.method == 'POST':
        try:
            # response from  daraja api upon payment attempt
            data = json.loads(request.body)
            print("received callback data " , data)
            stk_callback = data.get('Body',{}).get('stkCallback',{})
            result_code = stk_callback.get('ResultCode',None)
            result_desc = stk_callback.get('ResultDesc','')
            transaction_id = stk_callback.get('CheckoutRequestID',None)
            print(transaction_id,result_code)

            if transaction_id:
                transaction = Transaction.objects.filter(transaction_id=transaction_id).first()
                print("my transaction in db ", transaction)
                if transaction:
                    if result_code == 0:
                        callback_metadata = stk_callback.get('CallbackMetadata',{}).get('Item',[])
                        receipt_number = next((item.get('Value') for item in callback_metadata if item.get('Name') == 'MpesaReceiptNumber'), None)
                        amount = next((item.get('Value') for item in callback_metadata if item.get('Name') == 'Amount'), None)
                        transaction_date_str = next((item.get('Value') for item in callback_metadata if item.get('Name') == 'TransactionDate'), None)
                        # cleaning our transaction date screen
                        transaction_date = None
                        if transaction_date_str:
                            transaction_date = datetime.strptime(str(transaction_date_str), '%Y%m%d%H%M%S')

                        # updating transaction fields
                        transaction.mpesa_receipt_number = receipt_number
                        transaction.transaction_date = transaction_date
                        transaction.amount = amount
                        transaction.status = "Success"
                        transaction.description = "Payment Successful"
                        transaction.save()
                        print(f"Transaction {transaction_id} - {transaction.status} updated successfully")

                        ## TODO :  SEND EMAIL
                        if transaction.email:
                            subject = "Payment Receipt Confirmation"
                            message = (
                                f"Dear {transaction.name}, \n\n"
                                f"Thank you for your payment of {transaction.amount}"
                                f"Your MPESA confirmation receipt is {transaction.mpesa_receipt_number}"
                                "Best Regards , \n"
                                "STK PUSH"
                            )
                            html_message = (
                                f"<p>Dear {transaction.name},</p>"
                                f"<p>Thank you for your payment of {transaction.amount}</p>"
                                f"<p>Your MPESA confirmation receipt is {transaction.mpesa_receipt_number}</p>"
                                f"<p>Best Regards, STK Push</p>"
                            )
                            send_mail(subject,message,'carencherotich41@gmail.com',[transaction.email]
                                      ,fail_silently=False,html_message=html_message,)
                            print("Payment receipt email sent successfully")

                    elif result_code == 1:
                        transaction.status = "Failed"
                        transaction.description = result_desc
                        transaction.save()
                        print(f"Transaction {transaction_id} - {result_desc} failed.")
                    elif result_code == 1032:
                        transaction.status = "Cancelled"
                        transaction.description = "Transaction Cancelled by User"
                        transaction.save()
                        print(f"Transaction {transaction_id} marked as cancelled.")

            return JsonResponse({"message": "callback received and processed"}, status=200)

        except Exception as e:
            print(f"Error processing callback {e}")
            return JsonResponse({"error": f"Error processing callback {e}"}, status=500)

    return JsonResponse({"error" : "Invalid request method"}, status=400)


def check_status(request, transaction_id):
    # get the transaction needed for the process
    transaction = Transaction.objects.filter(id=transaction_id).first()
    if not transaction:
        return JsonResponse({"status": "failed" , "message": "Transaction not found"}, status=400)

    '''
    on stk prompt the transaction status is pending 
    on successful payments the transaction status is success 
    on failure the transaction status is failed 
    on cancellation the transaction status is canceled
    '''

    if transaction.status == "Success":
        return JsonResponse({"status": "Success", "message": "Payment Successful"}, status=200)
    elif transaction.status == "Failed":
        return JsonResponse({"status": "Failed", "message": "Payment Failed"}, status=200)
    elif transaction.status == "Cancelled":
        return JsonResponse({"status": "Cancelled", "message": "Transaction was Cancelled"}, status=200)
    else:
        return JsonResponse({"status": "Pending", "message": "Transaction still being processed."}, status=400)


def payment_success(request):
    return render(request,"payment_success.html")

def payment_failed(request):
    return render(request,"payment_failed.html")

def payment_cancelled(request):
    return render(request,"payment_cancelled.html")