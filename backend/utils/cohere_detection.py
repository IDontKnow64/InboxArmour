import cohere, os
import numpy as np
import re
import nltk

api_key = os.getenv("CO_API_KEY")

co = cohere.ClientV2(api_key)

def add_punctuation(line):
    # Strip extra spaces at the start and end of the line
    line = line.strip()
    if line and not line[-1] in ['.', '?', '!',":"]:
        return line + '.'
    return line

def detect_scam(email_content):

    # Universal naming scheme
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "email_test.txt")

    response = co.chat(
        model="command-a-03-2025",
        messages=[
                {  
                    "role": "system",
                    "content": "You respond with only either 'scam' or 'safe' for the given email"
                },
                {
                "role": "user",
                "content": email_content,
                }
            ],
        temperature = 0.0
    )

    print(response.message.content[0].text)

    if (response.message.content[0].text == "scam"):
        lines = email_content.split('\n')
        processed_lines = [add_punctuation(line) for line in lines]
        processed_email_content = '\n'.join(processed_lines)
        clean_content = re.sub(r'•⁠  ', '-', processed_email_content)
        clean_content = re.sub(r':', '.', clean_content)
        documents = nltk.sent_tokenize(clean_content)

        doc_emb = co.embed(
            texts=documents,
            model="embed-english-v3.0",
            input_type="search_document",
            embedding_types=["float"],
        ).embeddings.float

        query = "Which parts of an email indicates that it is a scam?"

        query_emb = co.embed(
            texts=[query],
            model="embed-english-v3.0",
            input_type="search_query",
            embedding_types=["float"],
        ).embeddings.float

        scores = np.dot(query_emb, np.transpose(doc_emb))[0]
        scores_max = scores.max()
        scores_norm = (scores) / (scores_max)
        # Sort and filter documents based on scores
        top_n = 5
        top_doc_idxs = np.argsort(-scores)[:top_n]

        top_docs = "\n"
        
        for idx, docs_idx in enumerate(top_doc_idxs):
            rank = (f"Rank: {idx+1}")
            reasons = (f"Document: {documents[docs_idx]}\n")
            originalScore = scores_norm[docs_idx]*100
            score= (f"Score: {originalScore}.2f%\n")
            top_docs += (f"Phrase {idx+1}:{documents[docs_idx]}\n")

        response = co.chat(
        model="command-a-03-2025",
        messages=[
                {  
                    "role": "system",
                    "content": "Explain why each phrase given suggests the email is a scam in the following format \nPhrase 1:\nPhrase 2: and so on"
                },
                {
                "role": "user",
                "content": email_content+top_docs,
                }
            ],
        temperature = 0.1
        )

        #print (response.message.content[0].text)
        reasons = re.findall(r'\*\*Reason:\*\*(.*?)\n', response.message.content[0].text)
        cleaned_reasons = [reason.strip() for reason in reasons]
        return ["Scam", cleaned_reasons, round(originalScore)]
    else:
        return ["Safe", "Reasons", 100] 


def summarize_email(email_body):
    """
    Summarizes the email content to focus on key points.
    :param email_body: The text content of the email.
    :return: A summarized version of the email.
    """
    try:
        response = co.summarize(
            model="command-r",
            text=email_body,
            length="short",
            format="paragraph"
        )
        return response.summary  # Return summarized email
    except Exception as e:
        print(f"Error summarizing email: {e}")
        return email_body  # Fall back to full email if summarization fails

def classify_email(email_body, descriptions):
    """
    Uses AI to classify a summarized email into one of the given folder descriptions.

    :param email_body: The text content of the email.
    :param descriptions: A dictionary where keys are classification labels and values are folder descriptions.
    :return: The most relevant classification label.
    """
    summary = summarize_email(email_body)  # Summarize email before classification
    labels = list(descriptions.keys())  # Extract classification labels

    try:
        response = co.classify(
            model="embed-english-v3.0",
            inputs=[summary],  # Use summarized email instead of full body
            examples=[(desc, label) for label, desc in descriptions.items()],
        )

        if response.classifications:
            return response.classifications[0].prediction  # Return the best-matching label

    except Exception as e:
        print(f"Error classifying email: {e}")

    return "Uncategorized"  # Default if classification fails
