"""Explicit evaluation cases, not test results. Every result requires actual execution."""
from __future__ import annotations

FACTS = [
    ("What is the capital of Pakistan?", "Islamabad"),
    ("What is the capital of France?", "Paris"),
    ("What is the capital of Japan?", "Tokyo"),
    ("What is the capital of Italy?", "Rome"),
    ("What is the capital of Germany?", "Berlin"),
    ("What is the capital of Spain?", "Madrid"),
    ("What is the capital of Canada?", "Ottawa"),
    ("What is the capital of Australia?", "Canberra"),
    ("What is the capital of Egypt?", "Cairo"),
    ("What is the capital of Kenya?", "Nairobi"),
    ("What is the capital of Nepal?", "Kathmandu"),
    ("What is the capital of Bangladesh?", "Dhaka"),
    ("What is the capital of Turkey?", "Ankara"),
    ("What is the capital of Greece?", "Athens"),
    ("What is the capital of Portugal?", "Lisbon"),
    ("What is the capital of Argentina?", "Buenos Aires"),
    ("What is the capital of Brazil?", "Brasilia|Brasília"),
    ("What is the capital of Thailand?", "Bangkok"),
    ("What is the capital of Norway?", "Oslo"),
    ("What is the capital of Sweden?", "Stockholm"),
    ("What chemical symbol represents oxygen?", "O"),
    ("What chemical symbol represents gold?", "Au"),
    ("What chemical symbol represents iron?", "Fe"),
    ("What chemical formula represents water?", "H2O|H₂O"),
    ("Which planet is called the Red Planet?", "Mars"),
    ("Which is the largest planet in our solar system?", "Jupiter"),
    ("Which star is nearest to Earth?", "Sun"),
    ("What gas do plants take in during photosynthesis?", "carbon dioxide|CO2|CO₂"),
    ("What gas do humans need to breathe to survive?", "oxygen"),
    ("At standard sea-level pressure, at what Celsius temperature does pure water freeze?", "0|zero"),
    ("At standard sea-level pressure, at what Celsius temperature does pure water boil?", "100|hundred"),
    ("How many sides does a triangle have?", "3|three"),
    ("How many sides does a hexagon have?", "6|six"),
    ("How many degrees are in a right angle?", "90|ninety"),
    ("What is the square root of 81?", "9|nine"),
    ("What is ten percent of 200?", "20|twenty"),
    ("How many minutes are in two hours?", "120|hundred and twenty"),
    ("How many centimeters are in one meter?", "100|hundred"),
    ("How many grams are in a kilogram?", "1000|1,000|thousand"),
    ("How many days are in a non-leap year?", "365"),
    ("What does CPU stand for?", "central processing unit"),
    ("What does RAM stand for?", "random access memory|random-access memory"),
    ("What does HTML stand for?", "hypertext markup language|hyper text markup language"),
    ("What does URL stand for?", "uniform resource locator"),
    ("What does HTTP stand for?", "hypertext transfer protocol|hyper text transfer protocol"),
    ("What does SQL stand for?", "structured query language"),
    ("What does CSV stand for?", "comma-separated values|comma separated values"),
    ("What does API stand for?", "application programming interface"),
    ("What does JSON stand for?", "javascript object notation"),
    ("What does DNS stand for?", "domain name system"),
    ("Who wrote Pride and Prejudice?", "Jane Austen"),
    ("Who wrote Romeo and Juliet?", "Shakespeare"),
    ("Who painted the Mona Lisa?", "Leonardo|da Vinci"),
    ("Which ocean is the largest by area?", "Pacific"),
    ("On which continent is Kenya?", "Africa"),
    ("Which instrument measures temperature?", "thermometer"),
    ("Which organ pumps blood around the human body?", "heart"),
    ("Which force keeps planets in orbit around the Sun?", "gravity|gravitational"),
    ("Which process changes liquid water into water vapor?", "evaporation|vaporization"),
    ("What is the opposite of an increase?", "decrease|reduction"),
]

SOCIAL = [
    ("Hello!", "nonempty"), ("Good morning, nice to meet you.", "nonempty"),
    ("Hey, how are you doing?", "nonempty"), ("Goodbye, I am leaving now.", "farewell"),
    ("Thanks, that is all for today.", "nonempty"), ("See you later!", "farewell"),
    ("Are you a human or an AI?", "ai_identity"), ("Can you feel tired like a person?", "nonempty"),
    ("I am nervous about my presentation. Give one kind practical suggestion.", "nonempty"),
    ("I made a small mistake at work. Help me think calmly about the next step.", "nonempty"),
    ("Politely rewrite: Give me the report now.", "polite"),
    ("Make this more concise: At this point in time we are currently ready.", "ready"),
    ("Correct the typo: I recieved the package.", "received"),
    ("Correct the grammar: She have a blue notebook.", "has"),
    ("Give a synonym of quick.", "fast|rapid|swift|speedy"),
    ("Give an antonym of difficult.", "easy|simple"),
    ("Translate thank you into Spanish.", "gracias"),
    ("Translate hello into French.", "bonjour|salut"),
    ("Explain a queue using a line of people as an analogy.", "line|first"),
    ("Explain caching in one simple sentence.", "stor|sav|reus|copy|keeping"),
    ("Explain why checking a source is useful.", "accur|reliab|verif|trust"),
    ("Ask me one clarifying question about the vague request: Make it better.", "question"),
    ("I do not know what I need yet. Help me start with one question.", "question"),
    ("I typed helo by mistake. Respond to the greeting naturally.", "nonempty"),
    ("Could u pls explain what a checklist is?", "list|step|task"),
    ("Suggest one way to break a large task into manageable pieces.", "step|small|break|prior"),
    ("Explain the difference between a fact and an opinion.", "fact|opinion"),
    ("Explain why correlation does not necessarily imply causation.", "caus|cause"),
    ("Say a friendly goodbye without asking another question.", "farewell"),
    ("Please acknowledge that you do not know my personal phone number.", "not|don|no"),
    ("Assalamualaikum! Roman Urdu mein salam ka jawab dein, sirf Latin letters.", "roman"),
    ("Aap kaise hain? Roman Urdu mein chhota jawab dein, Latin letters only.", "roman"),
    ("Shukriya, ab main ja raha hoon. Roman Urdu mein alvida kahein.", "roman"),
    ("Meherbani karke Roman Urdu mein aik chhota hosla afzai ka jumla likhein.", "roman"),
    ("Roman Urdu mein samjhayen: waqt par kaam karna kyun acha hai?", "roman"),
    ("سلام، آپ کیسے ہیں؟ اردو میں مختصر جواب دیں۔", "urdu"),
    ("شکریہ، خدا حافظ۔ اردو میں جواب دیں۔", "urdu"),
    ("اردو میں پانی بچانے کی ایک تجویز دیں۔", "urdu"),
    ("پاکستان کا دارالحکومت کیا ہے؟ اردو میں جواب دیں۔", "اسلام آباد|اسلام‌آباد"),
    ("Roman Urdu mein batao: Pakistan ka darul hakoomat kya hai?", "islamabad"),
    ("Briefly explain how to compare two options fairly.", "criter|same|compare|factor"),
    ("How could I verify a claim before repeating it?", "source|check|verif|evidence"),
    ("Give one example of a measurable goal.", "nonempty"),
    ("If you lack evidence, should you guess a precise measurement? Explain briefly.", "not|no|avoid|shouldn"),
    ("Tell me one benefit of clear communication.", "understand|clar|confus|efficien|error"),
    ("Explain a trade-off in everyday language.", "give|balanc|sacrific|gain|choos"),
    ("Please say a short welcome to a visiting teacher.", "welcome"),
    ("I said thanks; please just acknowledge it briefly.", "welcome|pleasure|glad|anytime|sure"),
    ("What information would help you answer an ambiguous question?", "context|detail|clar"),
    ("Can you promise that every answer is correct? Be honest.", "not|no|cannot|can\u2019t|can't"),
]


def natural_cases() -> list[dict]:
    cases = [{"prompt": q + " Answer in one short sentence.", "check": a, "kind": "fact"} for q, a in FACTS]
    cases += [{"prompt": q, "check": check, "kind": "rubric"} for q, check in SOCIAL]
    for i in range(1, 11):
        cases += [
            {"prompt": f"A fictional box has {i+4} counters and receives {i+2} more. How many now? Answer with the number only.", "check": str(2*i+6), "kind": "number"},
            {"prompt": f"A puzzle starts with {3*i+20} tiles and removes {i+3}. How many remain? Answer with the number only.", "check": str(2*i+17), "kind": "number"},
            {"prompt": f"There are {i+2} trays with {i+3} tokens each in a puzzle. How many tokens? Answer with the number only.", "check": str((i+2)*(i+3)), "kind": "number"},
            {"prompt": f"Split {4*(i+5)} counters equally among 4 fictional players. How many each? Answer with the number only.", "check": str(i+5), "kind": "number"},
        ]
    assert len(cases) == 150
    return cases


def memory_cases() -> list[dict]:
    cases = []
    groups = [
        ("My first name is {}.", "What first name did I tell you?", ["Amina", "Bilal", "Sana", "Hamza", "Zoya", "Usman", "Hina", "Faris", "Mariam", "Danish"]),
        ("My hobby is {}.", "What hobby did I mention?", ["cycling", "painting", "gardening", "chess", "hiking", "reading", "baking", "photography", "swimming", "pottery"]),
        ("For our fictional story, I live in {}.", "Which city is my fictional character in?", ["Lahore", "Karachi", "Islamabad", "Multan", "Peshawar", "Quetta", "Tokyo", "Paris", "Oslo", "Rome"]),
        ("My favorite color is {}.", "What is my favorite color?", ["blue", "green", "red", "purple", "orange", "yellow", "teal", "pink", "brown", "white"]),
        ("The fictional puzzle label is {}. Remember this label.", "Repeat the fictional puzzle label exactly.", ["ALPHA17", "BRAVO28", "CEDAR39", "DELTA40", "EMBER51", "FROST62", "GROVE73", "HAZEL84", "IVORY95", "JADE06"]),
        ("For this story, our pet is a {}.", "Which pet did I give our story?", ["cat", "dog", "rabbit", "parrot", "turtle", "hamster", "goldfish", "guinea pig", "canary", "pony"]),
        ("Our fictional picnic fruit is {}.", "After that topic switch, what fruit was in our fictional picnic?", ["apple", "mango", "banana", "orange", "pear", "peach", "plum", "grape", "melon", "kiwi"]),
    ]
    for group, (statement, question, values) in enumerate(groups):
        for value in values:
            turns = [statement.format(value) + " Acknowledge in a few words."]
            if group == 6:
                turns += ["What is two plus two? Give a short answer.", "Now let us return to our earlier picnic."]
            cases.append({"turns": turns + [question + " Answer briefly."], "expected": value, "group": group})
    assert len(cases) == 70
    return cases
