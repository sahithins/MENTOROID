
from flask_mongoengine import MongoEngine
from datetime import datetime, timedelta
# from mongoengine import CASCADE
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
    role = db.StringField(default="user")  # insert here manually in database for admin role

    def __repr__(self):
        return f"User('{self.fullname}', '{self.email}', '{self.image_file}')"

class Mentor(db.Document):
    '''
    Mentor's Login credentials
    '''
    fullname = db.StringField(required=True)
    password = db.StringField(required=True)
    email = db.StringField(required=True, unique=True)
    phonenumber = db.StringField(required=True)
    image_file = db.StringField(default="default.jpg")
    qualification = db.StringField()
    experience = db.StringField()
    linkedin = db.StringField()
    resume_file = db.StringField()
    status = db.BooleanField(default=False)

    def __repr__(self):
        return f"Mentor('{self.fullname}', '{self.email}')"

class Content(db.Document):
    '''
    Creates Materials table with columns course_name, title, file_type, description, upload_file
    '''
    course_name = db.StringField(required=True)
    title = db.StringField(required=True)
    file_type = db.StringField(required=True)
    description = db.StringField()
    upload_file = db.StringField(required=True)
    date_uploaded = db.DateTimeField(default=datetime.utcnow)
    
    def __repr__(self):
        return f"Content('{self.course_name}', '{self.title}', '{self.description}')"

class Courses(db.Document):
    '''
    Creates Courses table with columns course_name, mentor_name, summary, course_image, 
    course_price
    '''
    course_name = db.StringField(required=True)
    mentor_email = db.StringField()
    summary = db.StringField(required=True)
    course_image = db.StringField()

    def __repr__(self):
        return f"Courses('{self.course_name}', '{self.course_price}', '{self.summary}')"

class Enrollment(db.Document):
    '''
    Creates Enrollment table to track which users are enrolled in which courses
    '''
    user_id = db.StringField(required=True)
    course_id = db.StringField()
    enrollment_date = db.DateTimeField(default=datetime.utcnow)
    expire_date = db.DateTimeField()
    status = db.StringField(default="active")  # e.g., active, completed, dropped

    def __repr__(self):
        return f"Enrollment('user_id: {self.user_id}', 'course_id: {self.course_id}', 'status: {self.status}')"
    
    @classmethod
    def update_enrollment_status(cls):
        # Get the current date and time
        now = datetime.utcnow()
        # Find all enrollments where the expire_date has passed
        expired_enrollments = cls.objects(expire_date__lt=now)
        for enrollment in expired_enrollments:
            enrollment.delete()

class Feedbacks(db.Document):
    user_name = db.StringField(required=True)
    user_email = db.StringField(required=True)
    mentor_name = db.StringField(required=True)
    course_name = db.StringField(required=True)
    rating = db.StringField(required=True)
    feedback = db.StringField(required=True)
    suggestions = db.StringField()
    date_posted = db.DateTimeField(default=datetime.utcnow)

    def __repr__(self):
        return f"Feedbacks('user_email: {self.user_email}', 'mentor: {self.mentor_name}', 'rating: {self.rating}, 'feedback: {self.feedback}')"


    