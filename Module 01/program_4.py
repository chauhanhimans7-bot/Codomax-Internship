# Program 4: List operations on student marks
marks = [78, 85, 92, 67, 88]

print("Marks:", marks)
print("Total:", sum(marks))
print("Average:", sum(marks) / len(marks))
print("Highest:", max(marks))
print("Lowest:", min(marks))

marks.append(95)
print("After adding a new mark:", marks)
print("Sorted:", sorted(marks))


'''
OUTPUT 

Marks: [78, 85, 92, 67, 88]
Total: 410
Average: 82.0
Highest: 92
Lowest: 67
After adding a new mark: [78, 85, 92, 67, 88, 95]
Sorted: [67, 78, 85, 88, 92, 95]
'''