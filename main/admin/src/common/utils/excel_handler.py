import pandas as pd
from flask import current_app

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def validate_student_excel(file):
    """
    Validate and process an Excel file containing student data.
    
    Expected columns (case-insensitive):
    - 'ROLL NO.'
    - 'Student Name'
    - 'Email Address'
    
    Returns:
    - success (bool), message (str), students_data (list of tuples: (roll_number, name, email))
    """
    try:
        df = pd.read_excel(file)
        # Normalize column names
        df.columns = [str(col).strip().lower() for col in df.columns]
        required_cols = ['roll no.', 'student name', 'email address']
        for col in required_cols:
            if col not in df.columns:
                return False, f"Missing required column: {col}", []
        valid_data = []
        errors = []
        for index, row in df.iterrows():
            roll_number = str(row['roll no.']).strip()
            name = str(row['student name']).strip()
            email = str(row['email address']).strip()
            if not roll_number.startswith('718123') or len(roll_number) != 11 or not roll_number.isdigit():
                errors.append(f"Row {index+2}: Invalid roll number format '{roll_number}'")
                continue
            if not name:
                errors.append(f"Row {index+2}: Missing student name")
                continue
            if not email or '@' not in email:
                errors.append(f"Row {index+2}: Invalid or missing email address")
                continue
            valid_data.append((roll_number, name, email))
        if not valid_data:
            return False, "No valid student data found in the file", []
        if errors:
            error_message = f"Processed with {len(errors)} errors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                error_message += f"\n...and {len(errors)-5} more errors"
            return True, error_message, valid_data
        return True, f"Successfully processed {len(valid_data)} student records", valid_data
    except Exception as e:
        return False, f"Error processing Excel file: {str(e)}", []

def validate_course_staff_excel(file):
    """
    Validate and process an Excel file containing course and staff data.
    
    Expected format:
    - Column 1: Course Code
    - Column 2: Course Name
    - Column 3: Teacher Name
    
    Returns:
    - success (bool), message (str), data (list of tuples: (course_code, course_name, teacher_name))
    """
    try:
        df = pd.read_excel(file)
        if len(df.columns) < 3:
            return False, "Excel file must have at least three columns: Course Code, Course Name, Teacher Name", []
        code_col = df.columns[0]
        name_col = df.columns[1]
        teacher_col = df.columns[2]
        valid_data = []
        errors = []
        for index, row in df.iterrows():
            course_code = str(row[code_col]).strip()
            course_name = str(row[name_col]).strip()
            teacher_name = str(row[teacher_col]).strip()
            if not course_code or not course_name or not teacher_name:
                errors.append(f"Row {index+2}: Missing data (Course Code, Name, or Teacher Name)")
                continue
            valid_data.append((course_code, course_name, teacher_name))
        if not valid_data:
            return False, "No valid course/staff data found in the file", []
        if errors:
            error_message = f"Processed with {len(errors)} errors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                error_message += f"\n...and {len(errors)-5} more errors"
            return True, error_message, valid_data
        return True, f"Successfully processed {len(valid_data)} records", valid_data
    except Exception as e:
        return False, f"Error processing Excel file: {str(e)}", []
