from flask_mongoengine import MongoEngine
from datetime import datetime, timedelta

db = MongoEngine()

class User(db.Document):
    fullname = db.StringField(required=True)
    password = db.StringField(required=True)
    age = db.IntField(required=True)
    phonenumber = db.StringField(required=True)
    email = db.StringField(required=True, unique=True)
    address = db.StringField(required=True)
    image_file = db.StringField(default="default.jpg")
    role = db.StringField(default="user")

    def __repr__(self):
        return f"User('{self.fullname}', '{self.email}', '{self.image_file}')"

class Mentor(db.Document):
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

    def get_resume_url(self):
        return f"{self.resume_file}" if self.resume_file else None

    def __repr__(self):
        return f"Mentor('{self.fullname}', '{self.email}', '{self.qualification}')"

class Content(db.Document):
    course_name = db.StringField(required=True)
    title = db.StringField(required=True)
    file_type = db.StringField(required=True)
    description = db.StringField()
    upload_file = db.StringField(required=True)
    date_uploaded = db.DateTimeField(default=datetime.utcnow)
    
    def __repr__(self):
        return f"Content('{self.course_name}', '{self.title}', '{self.description}')"

class Courses(db.Document):
    course_name = db.StringField(required=True)
    course_category = db.StringField()
    mentor_email = db.StringField()
    summary = db.StringField(required=True)
    course_image = db.StringField()

    def __repr__(self):
        return f"Courses('{self.course_name}', '{self.summary}')"

class Enrollment(db.Document):
    user_id = db.StringField(required=True)
    course_id = db.StringField()
    enrollment_date = db.DateTimeField(default=datetime.utcnow)
    expire_date = db.DateTimeField()
    status = db.StringField(default="active")

    def __repr__(self):
        return f"Enrollment('user_id: {self.user_id}', 'course_id: {self.course_id}', 'status: {self.status}')"
    
    @classmethod
    def update_enrollment_status(cls):
        now = datetime.utcnow()
        expired_enrollments = cls.objects(expire_date__lt=now)
        for enrollment in expired_enrollments:
            enrollment.delete()

class Feedbacks(db.Document):
    user_name = db.StringField(required=True)
    user_email = db.StringField(required=True)
    mentor_name = db.StringField(required=True)
    course_name = db.StringField(required=True)
    course_category = db.StringField(required=True)  # Added field
    rating = db.IntField(required=True, min_value=1, max_value=5)  # Changed to IntField
    feedback = db.StringField(required=True)
    suggestions = db.StringField()
    timestamp = db.DateTimeField(default=datetime.utcnow)  # Renamed from date_posted

    def __repr__(self):
        return f"Feedbacks({self.user_email}, {self.course_name}, Rating: {self.rating}/5)"