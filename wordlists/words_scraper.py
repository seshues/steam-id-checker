import json

with open('words_dictionary.json', 'r') as file:
    words = json.load(file)

#with open('words_list.txt', 'r') as file:
#    words = file.readlines()

exclude_chars = [
    '.',
    ',',
    '-',
    "'",
    '"',
    '!',
    '#',
    '^',
    '%',
    '&',
    '/',
    '+',
    '(',
    ')',
    '[',
    ']',
    '{',
    '}',
    '~',
    '*',
    '_',
    ';',
    ':',
    '<',
    '>',
    '@',
    '£',
    '$',
    '|'
]

filtered_words = [
    word.strip() for word in words
    if 3 <= len(word.strip()) <= 7 and not any(char in word for char in exclude_chars)
]

with open('wordlist.json', 'w') as outfile:
    json.dump(filtered_words, outfile, indent=2)

print(f"total words saved: {len(filtered_words)}")
