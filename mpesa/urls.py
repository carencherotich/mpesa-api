"""
URL configuration for mpesa_payment project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('stk_push/', views.stk_push, name='stk_push'),
    path('waiting/<int:transaction_id>/', views.waiting_page, name='waiting_page'),
    path('callback/', views.callback, name='callback'),
    path('check-status/<int:transaction_id>/', views.check_status, name='check-status'),
    path('payment-success/', views.payment_success, name='payment-success'),
    path('payment-failed/', views.payment_failed, name='payment-failed'),
    path('payment-cancelled/', views.payment_cancelled, name='payment-cancelled'),
]

