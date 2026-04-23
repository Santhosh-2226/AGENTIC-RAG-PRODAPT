from groq_compat import get_compat_client

client = get_compat_client()

response = client.messages.create(
    model="llama-3.3-70b-versatile",
    max_tokens=200,
    messages=[{
        "role": "user",
        "content": "The IPL 2023 winner was Chennai Super Kings. Based only on this evidence, answer: Which team won IPL 2023?"
    }]
)

print("Response:", response.content[0].text)