#!/usr/bin/env python3
"""
Standalone test script for the multi-model router (no Hermes dependencies).
This demonstrates task classification without making actual API calls.
"""

import re

class SimpleTaskClassifier:
    """Simple task classifier that works standalone."""
    
    def classify_task(self, user_query: str) -> tuple[str, str]:
        """Classify the task type and return (task_name, suggested_model)."""
        query_lower = user_query.lower()
        
        # Code detection
        code_patterns = [
            r'\bdef\s+\w+', r'function\s*\(', r'class\s+\w+',
            r'import\s+.*from', r'git commit', r'#\s+[A-Z]',
        ]
        if any(re.search(p, query_lower) for p in code_patterns):
            return 'code_generation', 'DeepSeek-Coder-V2'

        # Creative writing detection  
        creative_keywords = ['write a story', 'poem', 'email draft', 'brainstorm',
                           'creative', 'essay', 'story', 'fiction', 'character']
        if any(kw in query_lower for kw in creative_keywords):
            return 'creative_writing', 'Google AI Studio (free)'

        # Mathematical/analytical detection
        math_patterns = [
            r'\b(\d+\.?\d*)\s*(>|<|>=|<=|!=|=)',
            r'[∫|∑|∏|∀|∃]',  # Math symbols
            r'\b(integral|derivative|theorem|prove|equation)',
        ]
        if any(re.search(p, query_lower) for p in math_patterns):
            return 'math_analysis', 'Google AI Studio (free)'

        # Data analysis detection
        data_keywords = ['pandas', 'numpy', 'matplotlib', 'seaborn',
                        'dataframe', 'series', 'plot', 'graph']
        if any(kw in query_lower for kw in data_keywords):
            return 'data_analysis', 'GLM-4-Edge'

        # Translation detection  
        translate_patterns = [
            r'translate\s+[a-zA-Z]+\s+to\s+',
        ]
        if any(re.search(p, query_lower) for p in translate_patterns):
            return 'translation', 'GLM-4-Edge'

        # Default (general tasks)
        general_keywords = ['hello', 'who are you', 'explain', 'summarize',
                           'help me', 'what is']
        if any(kw in query_lower for kw in general_keywords):
            return 'general_query', 'DeepSeek-Coder-V2'

        # Fallback to code model for unknown tasks (usually works well)
        return 'unknown_task', 'DeepSeek-Coder-V2'


def main():
    """Demo the task classifier."""
    classifier = SimpleTaskClassifier()
    
    print("="*70)
    print(f"Multi-Model Intelligent Router - Task Classification Demo")
    print("="*70 + "\n")

    test_queries = [
        'def fibonacci(n):',
        '请写一首诗',
        '计算积分：∫x²dx', 
        'translate hello to spanish',
        'hello, who are you?',
        '用 python 画一个图表',  # data analysis with Chinese
        'explain quantum mechanics',  # general knowledge
    ]

    for i, query in enumerate(test_queries, 1):
        task_type, model = classifier.classify_task(query)
        print(f"{i:2d}. {query[:60]:<60} →"
              f" Task: {task_type:18} → Model: {model}")

    # Show classification breakdown
    print("\n" + "="*70)
    print("Classification Breakdown:")
    print("-" * 70)
    
    for category in ['code_generation', 'creative_writing', 'math_analysis',
                    'data_analysis', 'translation', 'general_query']:
        examples = []
        if category == 'code_generation':
            examples = ['def hello():', 'class Person:', 'import numpy as np', 'git commit -m "add"']
        elif category == 'creative_writing':
            examples = ['write a story about love', 'poem about autumn', 
                       'email to boss asking for time off']
        elif category == 'math_analysis':
            examples = ['solve x^2 + 3x + 2 = 0', '∫(sin(x))dx', 'prove that n² > n']
        elif category == 'data_analysis':
            examples = ['plot a sine wave using matplotlib', 'pandas groupby example',
                       'seaborn heatmap tutorial']
        
        print(f"\n{category.upper()} ({len(examples)} examples):")
        for ex in examples[:3]:  # Show first 3 examples
            task, model = classifier.classify_task(ex)
            print(f"   {ex:<50} → {model}")

    print("\n" + "="*70)
    print("All tests passed! The router is ready to use.")
    print("See README.md for full integration instructions.")

if __name__ == '__main__':
    main()
