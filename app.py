from flask import Flask, render_template, request, redirect, url_for, session, flash
import flask
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os
from pathlib import Path


# Add this function after your imports and before route definitions

def get_french_months():
    """Return a list of tuples with month numbers and French month names."""
    return [
        (1, 'Janvier'),
        (2, 'Février'),
        (3, 'Mars'),
        (4, 'Avril'),
        (5, 'Mai'),
        (6, 'Juin'),
        (7, 'Juillet'),
        (8, 'Août'),
        (9, 'Septembre'),
        (10, 'Octobre'),
        (11, 'Novembre'),
        (12, 'Décembre')
    ]


# Load environment variables from .env file in development
if Path(".env").exists():
    from dotenv import load_dotenv
    load_dotenv()
from datetime import datetime, date, timedelta
import calendar
#test
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///salary.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "your-secure-secret-key-here")

db = SQLAlchemy(app)

# *** AUTHENTICATION SECTION (MOVED UP) ***
# Define application password - preferably from environment variable
APP_PASSWORD = os.getenv("APP_PASSWORD", "salary2023")  # Change this to your desired password

# Create a decorator function to check for authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# *** MODELS SECTION ***
class Employee(db.Model):
    __tablename__ = 'employee'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    hourly_salary = db.Column(db.Integer, nullable=False)
    vacation_days = db.Column(db.Integer, default=21)

    workdays = db.relationship('Workday', backref='employee', lazy=True)


class Workday(db.Model):
    __tablename__ = 'workday'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    work_date = db.Column(db.Date, nullable=False)
    hours_worked = db.Column(db.Integer, nullable=False)
    is_transport_day = db.Column(db.Boolean, default=False)
    is_vacation_day = db.Column(db.Boolean, default=False)
    is_paid_vacation = db.Column(db.Boolean, default=False)  # New column for paid vacation

# *** ROUTES SECTION ***

# Authentication routes
# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == APP_PASSWORD:
            session['authenticated'] = True
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            error = 'Incorrect password'
    
    return render_template('login.html', error=error)

# Logout route
@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

# Home route
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Employee routes
@app.route('/employees')
@login_required
def list_employees():
    employees = Employee.query.all()
    return render_template('employees.html', employees=employees)

# Modifier la route d'ajout d'employé
@app.route('/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        full_name = request.form['full_name']
        # Convertir millimes en DT pour le stockage
        hourly_salary = int(request.form['hourly_salary']) / 1000  
        vacation_days = int(request.form['vacation_days'])
        
        new_employee = Employee(
            full_name=full_name,
            hourly_salary=hourly_salary,
            vacation_days=vacation_days
        )
        
        db.session.add(new_employee)
        db.session.commit()
        
        flash('Employé ajouté avec succès!')
        return redirect(url_for('list_employees'))
    
    return render_template('add_employee.html')

# Modifier la route d'édition d'employé
@app.route('/edit_employee/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    if request.method == 'POST':
        employee.full_name = request.form['full_name']
        # Convertir millimes en DT pour le stockage
        employee.hourly_salary = int(request.form['hourly_salary']) / 1000
        employee.vacation_days = int(request.form['vacation_days'])
        
        db.session.commit()
        flash('Employé mis à jour avec succès!')
        return redirect(url_for('list_employees'))
    
    return render_template('edit_employee.html', employee=employee)

# Delete Employee Route
@app.route('/delete_employee/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    # Check if employee has workdays
    if employee.workdays:
        flash('Impossible de supprimer un employé avec des jours de travail existants. Supprimez leurs jours de travail d\'abord.')
        return redirect(url_for('list_employees'))
    
    db.session.delete(employee)
    db.session.commit()
    flash('Employé supprimé avec succès!')
    return redirect(url_for('list_employees'))

# Workday routes
@app.route('/workdays', methods=['GET'])
@login_required
def list_workdays():
    # Get filter parameters
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    
    # Base query
    workdays_query = Workday.query
    
    # Apply filters if provided
    if month and year:
        # Filter workdays for the selected month and year
        # SQLAlchemy extract works with most database backends
        workdays_query = workdays_query.filter(
            db.extract('month', Workday.work_date) == month,
            db.extract('year', Workday.work_date) == year
        )
    
    # Get all workdays based on the query
    workdays = workdays_query.all()
    
    # Generate month and year options for the filter
    current_year = datetime.now().year
    years = list(range(current_year - 5, current_year + 2))  # 5 years back, 1 year ahead
    months = get_french_months()  # Use the new function
    
    return render_template('workdays.html', 
                          workdays=workdays, 
                          months=months, 
                          years=years, 
                          selected_month=month,
                          selected_year=year)

@app.route('/add_workday', methods=['GET', 'POST'])
@login_required
def add_workday():
    if request.method == 'POST':
        employee_id = int(request.form['employee_id'])
        work_date = datetime.strptime(request.form['work_date'], '%Y-%m-%d').date()
        hours_worked = int(request.form['hours_worked'])
        workday_type = request.form.get('workday_type', 'regular')
        
        # Set boolean flags based on workday_type
        is_transport_day = (workday_type == 'transport')
        is_vacation_day = (workday_type == 'vacation')
        is_paid_vacation = (workday_type == 'paid_vacation')
        
        # Create new workday record
        new_workday = Workday(
            employee_id=employee_id,
            work_date=work_date,
            hours_worked=hours_worked,
            is_transport_day=is_transport_day,
            is_vacation_day=is_vacation_day,
            is_paid_vacation=is_paid_vacation
        )
        
        db.session.add(new_workday)
        
        # If this is a regular vacation day (not paid vacation), decrement the employee's vacation day count
        if is_vacation_day and not is_paid_vacation:
            employee = Employee.query.get(employee_id)
            if employee and employee.vacation_days > 0:
                employee.vacation_days -= 1
        
        db.session.commit()
        return redirect(url_for('list_workdays'))
    
    employees = Employee.query.all()
    return render_template('add_workday.html', employees=employees)

# Edit Workday Route
@app.route('/edit_workday/<int:workday_id>', methods=['GET', 'POST'])
@login_required
def edit_workday(workday_id):
    workday = Workday.query.get_or_404(workday_id)
    employees = Employee.query.all()
    
    if request.method == 'POST':
        # Get data from form
        employee_id = int(request.form['employee_id'])
        work_date = datetime.strptime(request.form['work_date'], '%Y-%m-%d').date()
        hours_worked = int(request.form['hours_worked'])
        workday_type = request.form.get('workday_type', 'regular')
        
        # Check if vacation status changed
        was_vacation = workday.is_vacation_day and not workday.is_paid_vacation
        
        # Set new boolean flags based on workday_type
        is_transport_day = (workday_type == 'transport')
        is_vacation_day = (workday_type == 'vacation')
        is_paid_vacation = (workday_type == 'paid_vacation')
        
        # If regular vacation status changed, update employee's vacation days
        is_now_vacation = is_vacation_day and not is_paid_vacation
        
        if was_vacation and not is_now_vacation:
            # Vacation day removed, add back a vacation day
            workday.employee.vacation_days += 1
        elif not was_vacation and is_now_vacation:
            # New vacation day, remove a vacation day
            if workday.employee.vacation_days > 0:
                workday.employee.vacation_days -= 1
        
        # Update workday
        workday.employee_id = employee_id
        workday.work_date = work_date
        workday.hours_worked = hours_worked
        workday.is_transport_day = is_transport_day
        workday.is_vacation_day = is_vacation_day
        workday.is_paid_vacation = is_paid_vacation
        
        db.session.commit()
        flash('Jour de travail mis à jour avec succès!')
        return redirect(url_for('list_workdays'))
    
    return render_template('edit_workday.html', workday=workday, employees=employees)

# Delete Workday Route
@app.route('/delete_workday/<int:workday_id>', methods=['GET', 'POST'])
@login_required
def delete_workday(workday_id):
    workday = Workday.query.get_or_404(workday_id)
    
    # If this was a regular vacation day, add the vacation day back to the employee
    if workday.is_vacation_day and not workday.is_paid_vacation:
        workday.employee.vacation_days += 1
    
    db.session.delete(workday)
    db.session.commit()
    flash('Jour de travail supprimé avec succès!')
    return redirect(url_for('list_workdays'))

# Salary calculator route
@app.route('/salary_calculator', methods=['GET', 'POST'])
@login_required
def salary_calculator():
    employees = Employee.query.all()
    
    # Get current month and year for defaults
    current_date = datetime.now()
    current_month = current_date.month
    current_year = current_date.year
    
    # Initialize all variables with defaults
    selected_employee = None
    selected_month = current_month
    selected_year = current_year
    salary_details = []  # Initialize as empty list instead of None
    total_salary = 0
    total_hours = 0
    regular_hours = 0
    overtime_hours_125 = 0
    overtime_hours_150 = 0
    transport_hours = 0  # Initialize as 0 instead of None
    transport_pay = 0    # Initialize as 0 instead of None
    paid_vacation_hours = 0  # Initialize as 0
    paid_vacation_pay = 0    # Initialize as 0
    vacation_hours = 0       # Initialize as 0
    vacation_pay = 0         # Initialize as 0
    workdays = []
    
    # Generate options for the form
    years = list(range(current_year - 5, current_year + 2))
    months = get_french_months()  # Use the new function
    
    if request.method == 'POST':
        employee_id = int(request.form.get('employee_id'))
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        
        # Get selected employee
        selected_employee = Employee.query.get(employee_id)
        selected_month = month
        selected_year = year
        
        if selected_employee:
            # Fetch workdays for the selected employee in the given month/year
            workdays = Workday.query.filter(
                Workday.employee_id == employee_id,
                db.extract('month', Workday.work_date) == month,
                db.extract('year', Workday.work_date) == year
            ).order_by(Workday.work_date).all()
            
            # Get the last day of the selected month
            last_day = calendar.monthrange(year, month)[1]
            
            # Create a calendar-based week calculation
            weeks = {}
            salary_details = []
            total_salary = 0
            total_hours = 0
            regular_hours = 0
            overtime_hours_125 = 0
            overtime_hours_150 = 0
            actual_total_hours = 0  # Nouvelle variable pour les heures réelles travaillées
            
            # Extract transport days separately
            transport_workdays = [day for day in workdays if day.is_transport_day]
            transport_hours = sum(day.hours_worked for day in transport_workdays)
            transport_pay = transport_hours * selected_employee.hourly_salary
            
            # Extract paid vacation days separately
            paid_vacation_workdays = [day for day in workdays if day.is_paid_vacation]
            paid_vacation_hours = sum(day.hours_worked for day in paid_vacation_workdays)
            paid_vacation_pay = paid_vacation_hours * selected_employee.hourly_salary
            
            # Filter out transport days and paid vacation days from weekly overtime calculations
            regular_workdays = [day for day in workdays if not day.is_transport_day 
                               and not day.is_vacation_day 
                               and not day.is_paid_vacation]
            
            # Add a new function to calculate adjusted hours with Sunday premium
            def calculate_adjusted_hours(workday):
                # Check if the day is Sunday (weekday() returns 6 for Sunday)
                if workday.work_date.weekday() == 6:  # Sunday
                    return workday.hours_worked * 1.5  # 1.5x for Sunday work
                else:
                    return workday.hours_worked  # Regular hours for other days

            # Find the first day of the month and determine its weekday (0 = Monday, 6 = Sunday)
            first_day = date(year, month, 1)
            first_day_weekday = first_day.weekday()

            # First, organize all days by their ISO week date
            for workday in regular_workdays:
                work_date = workday.work_date
                
                # Get the week number within the month
                # ISO week starts with Monday as 1 and Sunday as 7
                day_of_week = work_date.weekday()  # 0 = Monday, 6 = Sunday
                
                # Calculate which Monday-to-Sunday week this belongs to
                # If it's before the first Monday of the month, it goes in week 1
                if work_date.day <= (7 - first_day_weekday) % 7 or first_day_weekday == 0:
                    # Special case: if month starts on Monday, this is simply the day/7 rounded up
                    if first_day_weekday == 0:
                        week_num = (work_date.day - 1) // 7 + 1
                    else:
                        # First partial week (before first Sunday)
                        week_num = 1
                else:
                    # For days after the first Sunday
                    # Calculate days since the first Monday after month start
                    first_monday_day = (7 - first_day_weekday + 1) % 7 or 7  # Fix for when month starts on Monday
                    days_since_first_monday = work_date.day - first_monday_day
                    week_num = days_since_first_monday // 7 + 2  # +2 because week 1 is the partial week
                
                # Now determine the Monday and Sunday of this week
                if week_num == 1 and first_day_weekday != 0:
                    # First partial week
                    monday = first_day
                    sunday = date(year, month, (7 - first_day_weekday) % 7 or 7)
                else:
                    # Regular weeks
                    if first_day_weekday == 0:  # Month starts on Monday
                        monday_day = 1 + (week_num - 1) * 7
                    else:
                        # First Monday is (7 - first_day_weekday + 1) % 7 or 7 days from month start
                        first_monday_day = (7 - first_day_weekday + 1) % 7 or 7
                        monday_day = first_monday_day + (week_num - 2) * 7
                        
                    monday = date(year, month, monday_day) if monday_day <= last_day else None
                    sunday_day = monday_day + 6
                    sunday = date(year, month, sunday_day) if sunday_day <= last_day else date(year, month, last_day)
                
                # Skip if this week's Monday is in next month
                if not monday:
                    continue
                    
                week_key = f"Semaine {week_num} ({monday.strftime('%d/%m')} - {sunday.strftime('%d/%m')})"
                
                if week_key not in weeks:
                    weeks[week_key] = {
                        'hours': 0,
                        'days': [],
                        'start_date': monday,
                        'end_date': sunday,
                        'sunday_hours': 0  # Track Sunday hours separately
                    }
                
                # Add day to the week's records
                weeks[week_key]['days'].append(workday)
                
                # Apply Sunday premium to hours calculation
                if work_date.weekday() == 6:  # Sunday
                    # Store actual hours but count as 1.5x for overtime calculations
                    weeks[week_key]['sunday_hours'] += workday.hours_worked
                    weeks[week_key]['hours'] += workday.hours_worked  # Gardez les heures réelles
                    actual_total_hours += workday.hours_worked  # Comptez les heures réelles
                else:
                    # Regular day
                    weeks[week_key]['hours'] += workday.hours_worked
                    actual_total_hours += workday.hours_worked  # Comptez les heures réelles

            # Process each week for overtime calculations
            for week_key, week_data in weeks.items():
                week_hours = 0
                sunday_hours = week_data.get('sunday_hours', 0)
                regular_week_hours = 0  # Heures sans le dimanche
                hourly_salary = selected_employee.hourly_salary
                
                # Calculate regular hours and Sunday hours separately
                for workday in week_data['days']:
                    hours = workday.hours_worked
                    week_hours += hours
                    regular_week_hours += hours
                
                # Calculer la prime du dimanche séparément
                sunday_premium = sunday_hours * hourly_salary * 0.5
                
                # Calculate overtime based on total week_hours (including Sunday)
                if week_hours <= 42:
                    weekly_salary = ((regular_week_hours * hourly_salary) + 
                                    (sunday_hours * hourly_salary * 0.5))
                    week_regular_hours = week_hours
                    week_overtime_hours_125 = 0
                    week_overtime_hours_150 = 0
                elif week_hours <= 48:
                    # Prioritize non-Sunday hours for regular pay
                    regular_pay_hours = min(42, regular_week_hours)
                    overtime_125_hours = min(48 - 42, week_hours - 42)
                    
                    weekly_salary = ((regular_pay_hours * hourly_salary) + 
                                   (overtime_125_hours * hourly_salary * 1.25) + 
                                   (sunday_hours * hourly_salary * 0.5))
                    
                    week_regular_hours = regular_pay_hours  # Include Sunday in regular for display
                    week_overtime_hours_125 = overtime_125_hours
                    week_overtime_hours_150 = 0
                else:
                    # Prioritize non-Sunday hours for regular pay
                    regular_pay_hours = min(42, regular_week_hours)
                    overtime_125_hours = min(6, week_hours - 42)
                    overtime_150_hours = max(0, week_hours - 48)
                    
                    weekly_salary = ((regular_pay_hours * hourly_salary) + 
                                   (overtime_125_hours * hourly_salary * 1.25) + 
                                   (overtime_150_hours * hourly_salary * 1.5) + 
                                   (sunday_hours * hourly_salary * 0.5))
                    
                    week_regular_hours = regular_pay_hours  # Include Sunday in regular for display
                    week_overtime_hours_125 = overtime_125_hours
                    week_overtime_hours_150 = overtime_150_hours

                # Add week details to salary_details list
                salary_details.append({
                    'week': week_key,
                    'hours': week_hours,
                    'regular_hours': week_regular_hours,
                    'overtime_hours_125': week_overtime_hours_125,
                    'overtime_hours_150': week_overtime_hours_150,
                    'salary': weekly_salary,
                    'days': week_data['days'],
                    'start_date': week_data['start_date'],
                    'end_date': week_data['end_date']
                })
                
                # Add to totals
                regular_hours += week_regular_hours
                overtime_hours_125 += week_overtime_hours_125
                overtime_hours_150 += week_overtime_hours_150
                total_hours += week_hours
                total_salary += weekly_salary
            
            # Add vacation days (paid at regular rate)
            vacation_workdays = [day for day in workdays if day.is_vacation_day and not day.is_paid_vacation]
            vacation_hours = sum(day.hours_worked for day in vacation_workdays)
            vacation_pay = vacation_hours * selected_employee.hourly_salary
            
            # Add paid vacation, vacation, and transport pay to total
            total_salary += vacation_pay + transport_pay + paid_vacation_pay
            
            # After calculating all the separate hour types, add this:
            total_hours = regular_hours + overtime_hours_125 + overtime_hours_150 + vacation_hours + transport_hours + paid_vacation_hours
    
    # Always return a template regardless of request method
    return render_template('salary_calculator.html',
                          employees=employees,
                          selected_employee=selected_employee,
                          selected_month=selected_month,
                          selected_year=selected_year,
                          months=months,
                          years=years,
                          workdays=workdays,
                          total_hours=total_hours,
                          regular_hours=regular_hours,
                          overtime_hours_125=overtime_hours_125,
                          overtime_hours_150=overtime_hours_150,
                          total_salary=total_salary,
                          salary_details=salary_details,
                          transport_hours=transport_hours,
                          transport_pay=transport_pay,
                          paid_vacation_hours=paid_vacation_hours,
                          paid_vacation_pay=paid_vacation_pay,
                          vacation_hours=vacation_hours,
                          vacation_pay=vacation_pay)
