from flask import Flask, render_template, url_for, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import time
import board
import busio
import serial
import adafruit_fingerprint
import adafruit_character_lcd.character_lcd_i2c as character_lcd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SECRET_KEY'] = 'g1mo9je(e9jo0uv+(8(^1fl31dd%$5rldf04zm$^20am)z=c(h'
db = SQLAlchemy(app)


##### FINGERPRINT ######
uart = serial.Serial("/dev/ttyAMA0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

##### LCD #####
# Modify this if you have a different sized Character LCD
lcd_columns = 20
lcd_rows = 4

# Initialise I2C bus.
i2c = busio.I2C(board.SCL, board.SDA)  # uses board.SCL and board.SDA

# Initialise the lcd class
lcd = character_lcd.Character_LCD_I2C(i2c, lcd_columns, lcd_rows)


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fullname = db.Column(db.String(1000), nullable=False)
    date_added = db.Column(db.Date, default=date.today)

    def __repr__(self):
        return '<User %r>' % self.id

class Courses(db.Model, UserMixin):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)

    course_name = db.Column(db.String(255), nullable=False)
    course_code = db.Column(db.String(255), nullable=False)
    course_description = db.Column(db.String(1000), nullable=False)
    course_units = db.Column(db.String(255), nullable=False)
    course_year = db.Column(db.String(255), nullable=False)
    course_teacher = db.Column(db.ForeignKey('user.fullname'), nullable=False)
    date_added = db.Column(db.Date, default=date.today)

    teacher = db.Relationship('User', foreign_keys=course_teacher)
    def __repr__(self):
        return '<Courses %r>' % self.id
    
class Students(db.Model, UserMixin):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)

    fullname = db.Column(db.String(1000), nullable=False)
    course = db.Column(db.String(255), nullable=False)
    studentid = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(255), nullable=False)
    program = db.Column(db.String(255), nullable=False)
    year = db.Column(db.String(255), nullable=False)
    parentphone = db.Column(db.String(255), nullable=False)
    fingerprint = db.Column(db.LargeBinary, nullable=True)
    teacher_name = db.Column(db.String(1000), db.ForeignKey('user.fullname'), nullable=False)
    date_added = db.Column(db.Date, default=date.today)

    teacher = db.Relationship('User', foreign_keys=teacher_name)

    def __repr__(self):
        return '<Students %r>' % self.id

class History(db.Model, UserMixin):
    __tablename__ = 'history'
    id = db.Column(db.Integer, primary_key=True)

    studentid = db.Column(db.String(255), nullable=False)
    student_name = db.Column(db.String(1000), nullable=False)
    program = db.Column(db.String(255), nullable=False)
    year = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(255), default='Absent')
    date_timein = db.Column(db.Date, default=date.today)
    
    def __repr__(self):
        return '<History %r>' % self.id
    
@app.cli.command('createdb')
def db_create():
    db.create_all()
    print('Database created!')
@app.cli.command('dropdb')
def db_drop():
    db.drop_all()
    print('Database dropped!')
@app.cli.command('create-admin')
def db_seed():
    hashed_password = generate_password_hash('admin')
    user1 = User(username='admin', password=hashed_password, fullname='Admin')
    db.session.add(user1)
    db.session.commit()
    print('Database seeded!')

login_manager = LoginManager()
login_manager.login_view = 'index.html'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('index'))

################ LOGIN/LOGOUT ################
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.username == 'admin':
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('dashboard'))
    
    return render_template("login.html")

@app.route('/', methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username.lower()).first()

        if user and check_password_hash(user.password, password):
            login_user(user)

            if user.username == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Please check your login details and try again.')

    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

################ TEACHER DASHBOARD ################
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        return render_template("dashboard.html", fullname=current_user.fullname)
    
################ ATTENDANCE ################
@app.route('/attendance')
@login_required
def attendance():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        return render_template("attendance.html")
    
################ STUDENTS ################
@app.route('/students/list')
@login_required
def students_list():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        students = Students.query.filter_by(teacher_name=current_user.fullname).order_by(Students.date_added).all()

        return render_template("students-db.html", students=students)

@app.route('/students/add', methods=["POST", "GET"])
@login_required
def students_add():
    courses = Courses.query.all()

    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        if request.method == "POST":
            fullname = request.form.get('fullname')
            course = request.form.get('coursename')
            studentid = request.form.get('studentid')
            department = request.form.get('department')
            program = request.form.get('program')
            year = request.form.get('year')
            parentphone = request.form.get('parentphone')

            # Display message on the LCD while waiting for fingerprint scan
            lcd.clear()
            lcd.message = 'Register Fingerprint'

            finger.enroll_start(1)
            # Scan the fingerprint
            lcd.message = 'Waiting for finger...'
            while finger.get_image() != adafruit_fingerprint.OK:
                pass
            # Capture the fingerprint features
            while finger.image_2_tz(1) != adafruit_fingerprint.OK:
                pass

            # Save the features to database
            feature_data = finger.download_model(1)
            fingerprint = feature_data

            new_student = Students(fullname=fullname, course=course, studentid=studentid, department=department, program=program, year=year, parentphone=parentphone, fingerprint=fingerprint, teacher_name=current_user.fullname)

            db.session.add(new_student)
            db.session.commit()

            return redirect(url_for('students_list'))
        return render_template("students-add.html", courses=courses)
    
################ COURSES ################    
@app.route('/courses/list')
@login_required
def courses():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        courses = Courses.query.filter_by(course_teacher=current_user.fullname).order_by(Courses.date_added).all()

        return render_template("courses-db.html", courses=courses)
    
@app.route('/courses/add', methods=["POST", "GET"])
@login_required
def courses_add():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        if request.method == "POST":
            course_name = request.form.get('course_name')
            course_code = request.form.get('course_code')
            course_description = request.form.get('course_description')
            course_units = request.form.get('course_units')
            course_year = request.form.get('course_year')

            new_course = Courses(course_name=course_name, course_code=course_code, course_description=course_description, course_units=course_units, course_year=course_year, course_teacher=current_user.fullname)

            db.session.add(new_course)
            db.session.commit()

            return redirect(url_for('courses'))
        return render_template("courses-add.html")
    
################ ADMIN DASHBOARD ################
@app.route('/admin')
@login_required
def admin():
    return render_template("admin.html", fullname=current_user.fullname)

@app.route('/addteacher')
@login_required
def addteacher():
    return render_template("addteacher.html")

@app.route('/addteacher', methods=["POST"])
@login_required
def addteacher_post():
    fullname = request.form.get('fullname')
    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()
    
    if user:
        flash('Username Exists. Try another one.')
        return redirect(url_for('addteacher'))
    
    new_user = User(fullname=fullname, username=username.lower(), password=generate_password_hash(password, method='sha256'))

    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('admin'))

@app.route('/students')
@login_required
def students():
    students = Students.query.order_by(Students.date_added).all()

    return render_template("students.html", students=students)