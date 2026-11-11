# Program 5: Student Grade Calculator
def get_grade(average):
    if average >= 90:
        return "A"
    elif average >= 75:
        return "B"
    elif average >= 60:
        return "C"
    elif average >= 40:
        return "D"
    else:
        return "F"

subjects = int(input("Enter number of subjects: "))
marks = []

for i in range(1, subjects + 1):
    mark = float(input(f"Enter marks for subject {i}: "))
    marks.append(mark)

average = sum(marks) / len(marks)

print("\n--- Result ---")
print("Total marks :", sum(marks))
print("Average     :", round(average, 2))
print("Grade       :", get_grade(average))


'''
OUTPUT

Enter number of subjects: 3
Enter marks for subject 1: 45
Enter marks for subject 2: 56
Enter marks for subject 3: 70

--- Result ---
Total marks : 171.0
Average     : 57.0 
Grade       : D   
'''     