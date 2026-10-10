from app.rag import search

queries = [
    "return policy kya hai",                      # Roman Urdu
    "کیا میں پارسل کھول کر چیک کر سکتی ہوں؟",       # Urdu script
    "delivery charges kitne hain",
    "Do you deliver to Dubai?",                    # English
    # Out of scope: should score LOW
    "rider ne mere saath badtameezi ki",
    "aaj cricket match kaun jeeta",
]

for q in queries:
    print(f"\nQ: {q}")
    for r in search(q):
        print(f"   {r['score']:.3f}  {r['id']}")