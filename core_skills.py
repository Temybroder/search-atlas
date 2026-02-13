import random

# 1. Create a list of 10 random numbers between 1 and 20
random_numbers = [random.randint(1, 20) for _ in range(10)]
print("Random Numbers:", random_numbers)

# 2. Filter Numbers Below 10 (List Comprehension)
below_10_comprehension = [num for num in random_numbers if num < 10]
print("Below 10 (List Comprehension):", below_10_comprehension)

# 3. Filter Numbers Below 10 (Using filter)
below_10_filter = list(filter(lambda num: num < 10, random_numbers))
print("Below 10 (Using filter):", below_10_filter)
