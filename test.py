def calculate_stats(data):
    """Calculate basic statistics"""
    if not data:
        return None
    return {
        "mean": sum(data) / len(data),
        "min": min(data),
        "max": max(data)
    }

# Test
numbers = [1, 2, 3, 4, 5]
print(calculate_stats(numbers))