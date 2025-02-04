from django.shortcuts import render,redirect
from mainapp.models import *
import urllib.request
import urllib.parse
import random 
import ssl
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

# Create your views here.
def home(request):
    return render(request,'main/index.html')

def about(request):
    return render(request,'main/about.html')

def courses(request):
    return render(request,'main/courses.html')

def student(request):
    if request.method=='POST':
        user_email=request.POST.get('email')
        user_password=request.POST.get('password')
        print(user_email,user_password)

        user_data=User_Model.objects.get(email=user_email)
        print(user_data)
        
        if user_data.password==user_password:
            if user_data.otp_status=='verified' and user_data.user_status=='accepted':
                request.session['user_id']=user_data.user_id
                messages.success(request, 'You are logged in..')
                user_data.numberoftimeslogin += 1
                user_data.save()
                return redirect('user_dashboard')
            elif user_data.otp_status=='verified' and user_data.user_status=='pending':
                messages.info(request, 'Your Status is in pending')
                return redirect('student')
            else:
                messages.warning(request, 'Verify OTP...!')
                request.session['email']=user_data.email
                return redirect('registration')
        else:
            messages.error(request, 'Incorrect Credentials...!')
            return redirect('student')
    return render(request,'main/student.html')

def mentor(request):
    return render(request,'main/mentor.html')

def registration(request):
    if request.method == "POST":
        fullname = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        age = request.POST.get("age")
        address = request.POST.get("address")
        phone = request.POST.get("phonenumber")
        image = request.FILES["image"]
        # number = random.randint(1000, 9999)
        print(fullname,email,password,age,address,phone,image)
        try:
            data = User_Model.objects.get(email=email)
            messages.warning(
                request, "Email was already registered, choose another email..!"
            )
            return redirect("registration")
        except:
            # sendSMS(fullname, number, phone)
            User_Model.objects.create(
                fullname=fullname,
                email=email,
                phonenumber=phone,
                age=age,
                password=password,
                address=address,
                Image=image,
                # otp=number,
            )
            # mail_message = (
            #     f"Registration Successfully\n Your 4 digit Pin is below\n {number}"
            # )
            # print(mail_message)
            # send_mail("User Password", mail_message, settings.EMAIL_HOST_USER, [email])
            request.session["email"] = email
            messages.success(request, "Your account was created..")
            return redirect("student")
    return render(request,'main/registration.html')