# Program 3: Functions
def check_even_odd(n):
    return "Even" if n % 2 == 0 else "Odd"

def factorial(n):
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

print("7 is", check_even_odd(7))
print("10 is", check_even_odd(10))
print("Factorial of 5 =", factorial(5))



'''

OUTPUT 
7 is Odd
10 is Even
Factorial of 5 = 120
'''