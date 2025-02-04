from django.db import models
from django.utils import timezone

# Create your models here.
class User_Model(models.Model):
    user_id = models.AutoField(primary_key=True)
    fullname = models.CharField(max_length=50)
    password = models.TextField(max_length=50)
    email = models.EmailField(max_length=254)
    age = models.IntegerField(null=True)
    phonenumber = models.TextField(max_length=15)
    address = models.TextField(max_length=254)
    Image = models.FileField(upload_to='images/', null=True)
    datetime = models.DateTimeField(auto_now=True, null=True)
    user_status = models.TextField(default = 'pending', max_length=50, null = True)
    otp = models.IntegerField(null=True)
    otp_status = models.TextField(default='pending', max_length=60, null=True)
    last_login_time = models.TimeField(auto_now_add=True,null = True)
    last_login_date = models.DateField(auto_now_add=True,null = True)
    numberoftimeslogin = models.IntegerField(default=0, null=True)
    class Meta:
        db_table = 'user'

class Dataset_Model(models.Model):
   Data_id = models.AutoField(primary_key=True)
   Image = models.ImageField(upload_to='media/',null=True) 
   class Meta:
        db_table = "upload"