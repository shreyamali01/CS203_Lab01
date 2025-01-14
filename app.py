import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from pythonjsonlogger import jsonlogger

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'

#setting up JSON logging format
logger = logging.getLogger()
logHandler = logging.StreamHandler()

logFormatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
logHandler.setFormatter(logFormatter)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

#setting up TracerProvider and adding Jaeger exporter
trace.set_tracer_provider(TracerProvider())
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
FlaskInstrumentor().instrument_app(app)

#getting a tracer instance
tracer = trace.get_tracer("flask-app","1.0.0")

# Utility Functions
def load_courses():
    """Load courses from the JSON file."""
    if not os.path.exists(COURSE_FILE):
        return []  # Return an empty list if the file doesn't exist
    with open(COURSE_FILE, 'r') as file:
        return json.load(file)


def save_courses(data):
    """Save new course data to the JSON file."""
    courses = load_courses()  # Load existing courses
    courses.append(data)  # Append the new course
    with open(COURSE_FILE, 'w') as file:
        json.dump(courses, file, indent=4)


# Routes
@app.route('/')
def index():
    with tracer.start_as_current_span("index_route"):
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)
        return render_template('index.html')

@app.route('/catalog')
def course_catalog():
    with tracer.start_as_current_span("course_catalog_route"):
        #adding metadata to the spans
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)

        #debugging
        print(f"Created span for /catalog: {span}.")
    
        courses = load_courses()
        return render_template('course_catalog.html', courses=courses)


@app.route('/course/<code>')
def course_details(code):
    with tracer.start_as_current_span("course_details_route"):
        #ading metadata to the span
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)

        courses = load_courses()
        course = next((course for course in courses if course['code'] == code), None)
    
        if not course:
            flash(f"No course found with code '{code}'.", "error")
            return redirect(url_for('course_catalog'))
        return render_template('course_details.html', course=course)


#route to add a new course
@app.route('/add-course', methods=['GET', 'POST'])
def add_course():
     with tracer.start_as_current_span("add_course_route"):
         #adding metadata to the span
        span = trace.get_current_span()
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("http.method", request.method)

        if request.method == 'POST':
            #extracting the form data
            course_code = request.form.get('code')
            course_name = request.form.get('name')
            instructor = request.form.get('instructor')
            semester = request.form.get('semester')
            schedule = request.form.get('schedule', '')
            classroom = request.form.get('classroom', '')
            prerequisites = request.form.get('prerequisites', '')
            grading = request.form.get('grading', '')
            description = request.form.get('description', '')

            #validating required fields
            if not course_code or not course_name or not instructor or not semester or not schedule:
                missing_fields = []
                if not course_code:
                    missing_fields.append("course code")
                if not course_name:
                    missing_fields.append("course name")
                if not instructor:
                    missing_fields.append("instructor")
                if not semester:
                    missing_fields.append("semester")
                if not schedule:
                    missing_fields.append("schedule")
        
                #subsequent error message
                missing_fields_str = ", ".join(missing_fields)
                logging.error(f"Failed to add course: Missing required fields - {missing_fields_str}")
                flash(f"Please provide the following required fields: {missing_fields_str}.", "error")
                return redirect(url_for('add_course'))
            
            courses = load_courses()

            if any(course['code'] == course_code for course in courses):
                logging.error(f"Duplicate course code: {course_code}")
                flash("Course code already exists. Please use a unique code.", "error")
                return redirect(url_for('add_course'))

            # Save the course
            save_courses({
                'code': course_code,
                'name': course_name,
                'instructor': instructor,
                'semester': semester,  # Default semester to "N/A" if not provided
                'schedule':schedule,
                'classroom':classroom,
                'prerequisites':prerequisites,
                'grading':grading,
                'description':description
            })

            logging.info(f"Course added successfully: {course_code} - {course_name} by {instructor} for {semester}")
            flash("Course added successfully!", "success")
            return redirect(url_for('course_catalog'))

        # Render the form template for GET requests
        return render_template('add_course.html')


if __name__ == '__main__':
    app.run(debug=True,port=5001)
