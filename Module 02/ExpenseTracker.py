expenses = []

while True:
    print("\n===== EXPENSE TRACKER =====")
    print("1. Add Expense")
    print("2. View All Expenses")
    print("3. Show Total Spending")
    print("4. Exit")

    choice = input("Enter your choice: ")

    # Add a new expense
    if choice == "1":
        name = input("Enter expense name: ")

        try:
            amount = float(input("Enter expense amount: ₹"))

            if amount <= 0:
                print("Please enter an amount greater than zero.")
                continue

            expense = {
                "name": name,
                "amount": amount
            }

            expenses.append(expense)
            print("Expense added successfully!")

        except ValueError:
            print("Invalid amount! Please enter a number.")

    # View all expenses
    elif choice == "2":
        if len(expenses) == 0:
            print("No expenses recorded yet.")
        else:
            print("\nYour Expenses:")

            for index, expense in enumerate(expenses, start=1):
                print(
                    f"{index}. {expense['name']} - ₹{expense['amount']:.2f}"
                )

    # Calculate total spending
    elif choice == "3":
        total = sum(expense["amount"] for expense in expenses)
        print(f"Total Spending: ₹{total:.2f}")

    # Exit the program
    elif choice == "4":
        print("Thank you for using Expense Tracker!")
        break

    else:
        print("Invalid choice! Please select 1, 2, 3, or 4.")




'''
OUTPUT
PS C:\Users\Yuri\Desktop\codomax\Module 02> python ExpenseTracker.py

===== EXPENSE TRACKER =====
1. Add Expense        
2. View All Expenses  
3. Show Total Spending
4. Exit
Enter your choice: 1  
Enter expense name: food
Enter expense amount: ₹1000
Expense added successfully!

===== EXPENSE TRACKER =====
1. Add Expense
2. View All Expenses
3. Show Total Spending
4. Exit
Enter your choice: 1
Enter expense name: repairing
Enter expense amount: ₹1200
Expense added successfully!

===== EXPENSE TRACKER =====
1. Add Expense
2. View All Expenses
3. Show Total Spending
4. Exit
Enter your choice: 3
Total Spending: ₹2200.00

===== EXPENSE TRACKER =====
1. Add Expense
2. View All Expenses
3. Show Total Spending
4. Exit
Enter your choice: 4   
Thank you for using Expense Tracker!
PS C:\Users\Yuri\Desktop\codomax\Module 02> 
'''