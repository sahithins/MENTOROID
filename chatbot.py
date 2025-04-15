import os
import traceback
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from models import User, Courses, Enrollment, Unit, Lesson, CompletionStatus, Quiz

load_dotenv()

def get_all_courses_info():
    courses = Courses.objects.all()
    info = "Available Courses:\n"
    if not courses:
        return info + "No courses available at the moment.\n"
    for course in courses:
        info += f"- {course.course_name} (Category: {course.course_category}): {course.summary}\n"
    return info

def get_user_enrollment_details(user_email):
    user = User.objects(email=user_email).first()
    if not user:
        return "User not found.\n", []

    enrollments = Enrollment.objects(user_id=str(user.id), status='active')
    if not enrollments:
        return "You are not currently enrolled in any active courses.\n", []

    details = "Your Enrolled Courses & Progress:\n"
    enrolled_courses_objects = []

    for enrollment in enrollments:
        course = enrollment.course
        if not course:
            continue

        enrolled_courses_objects.append(course)
        details += f"\n--- Course: {course.course_name} ---\n"
        details += f"   - Enrollment Status: Active (Expires: {enrollment.expire_date.strftime('%Y-%m-%d') if enrollment.expire_date else 'N/A'})\n"

        completion_status = CompletionStatus.objects(user_email=user_email, course=course).first()
        units = Unit.objects(course=course).order_by('order')
        total_lessons_count = Lesson.objects(unit__in=units).count()
        completed_lessons_count = 0
        quiz_info = "Quiz: Not available or not taken yet."

        if completion_status:
            completed_lessons_count = len(completion_status.completed_lessons)
            if completion_status.quiz_taken:
                status = "Passed" if completion_status.quiz_passed else "Failed"
                score = f"{completion_status.quiz_score_percent}%" if completion_status.quiz_score_percent is not None else "N/A"
                quiz_info = f"Quiz Status: Taken, Result: {status}, Score: {score}"
            elif Quiz.objects(course=course).count() > 0:
                quiz_info = "Quiz Status: Available, Not Taken Yet."

        percentage = round((completed_lessons_count / total_lessons_count) * 100) if total_lessons_count > 0 else 0
        details += f"   - Lesson Progress: {completed_lessons_count}/{total_lessons_count} lessons completed ({percentage}%)\n"
        details += f"   - {quiz_info}\n"

        if units:
            details += "   - Course Structure:\n"
            for unit in units:
                details += f"      * Unit: {unit.title}\n"
                lessons = Lesson.objects(unit=unit).order_by('order')
                if lessons:
                    lesson_titles = [f"{l.title} ({'Completed' if completion_status and l in completion_status.completed_lessons else 'Pending'})" for l in lessons]
                    details += f"         - Lessons: {', '.join(lesson_titles)}\n"
                else:
                    details += f"         - Lessons: (No lessons in this unit)\n"
        else:
            details += "   - Course Structure: (No units defined for this course)\n"

    return details, enrolled_courses_objects

class MentoroidChatbot:
    def __init__(self, api_key=None):
        if not api_key:
            api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key not found. Set GROQ_API_KEY environment variable.")

        model_name = "gemma2-9b-it"

        self.llm = ChatGroq(
            temperature=0.7,
            groq_api_key=api_key,
            model_name=model_name
        )
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        self.prompt_template = None

    def _build_prompt(self, user_context):
        system_message = f"""You are a helpful AI assistant for the Mentoroid learning platform.
Your purpose is to answer user questions about courses based ONLY on the provided context.
Do not make up information or answer questions outside the scope of Mentoroid courses.
Be friendly and informative.

CONTEXT:
{user_context}
"""
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{user_query}")
        ])

    def get_response(self, user_email, user_query, chat_history=None):
        try:
            user_specific_details, _ = get_user_enrollment_details(user_email)
            all_courses_details = get_all_courses_info()
            full_context = f"{all_courses_details}\n{user_specific_details}"
            self._build_prompt(full_context)

            conversation_chain = LLMChain(
                llm=self.llm,
                prompt=self.prompt_template,
                memory=self.memory,
                verbose=False
            )

            response = conversation_chain.predict(user_query=user_query)
            return response

        except Exception as e:
            print(f"Error in chatbot get_response: {e}")
            traceback.print_exc()
            return "Sorry, I encountered an error trying to process your request. Please try again later."