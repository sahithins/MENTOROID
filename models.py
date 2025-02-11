
from flask_mongoengine import MongoEngine
from datetime import datetime

db = MongoEngine()

class User(db.Document):
    '''
    Creates User table with columns fullname, password, age, phonenumber, email, address, image_file
    '''
    fullname = db.StringField(required=True)
    password = db.StringField(required=True)
    age = db.IntField(required=True)
    phonenumber = db.StringField(required=True)
    email = db.StringField(required=True, unique=True)
    address = db.StringField(required=True)
    image_file = db.StringField(default="default.jpg")

    def __repr__(self):
        return f"User('{self.fullname}', '{self.email}', '{self.image_file}')"

class Queries(db.Document):
    '''
    Creates Queries table with columns fullname, email, phonenumber, subject, message
    '''
    fullname = db.StringField(required=True)
    email = db.StringField(required=True)
    phonenumber = db.StringField(required=True)
    subject = db.StringField(required=True)
    message = db.StringField(required=True)
    
    def __repr__(self):
        return f"Queries('{self.fullname}', '{self.email}', '{self.subject}')"

class Materials(db.Document):
    '''
    Creates Materials table with columns course_name, title, description, upload_file
    '''
    course_name = db.StringField(required=True)
    title = db.StringField(required=True)
    description = db.StringField(required=True)
    upload_file = db.StringField(required=True)
    date_uploaded = db.DateTimeField(default=datetime.utcnow)
    
    def __repr__(self):
        return f"Queries('{self.fullname}', '{self.email}', '{self.subject}')"


    