import json
from typing import List, Dict, Any

class DataProcessor:
    def __init__(self):
        self.data = []
    
    def load_from_file(self, filepath: str):
        with open(filepath, 'r') as f:
            self.data = json.load(f)
        return self
    
    def filter_by_key(self, key: str, value: Any) -> List[Dict]:
        return [item for item in self.data if item.get(key) == value]
    
    def calculate_average(self, key: str) -> float:
        values = [item[key] for item in self.data if key in item]
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    def save_results(self, filepath: str, results: List[Dict]):
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)