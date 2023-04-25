from typing import List
import torch
import torch.nn.functional as F

from tenacity import retry, wait_random_exponential, stop_after_attempt

from services.utils import mean_pooling


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def get_mpnet_embeddings(texts: List[str], tokenizer, model) -> List[List[float]]:
    """
    Embed texts using all-mpnet-base-v2 model.

    Args:
        texts: The list of texts to embed.

    Returns:
        A list of embeddings, each of which is a list of floats.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    try:
        assert tokenizer is not None and model is not None, "tokenizer and model should not be None"
        # Tokenize
        encoded_input = tokenizer(texts, padding=True, truncation=True, return_tensors='pt')

        # Compute token embeddings
        with torch.no_grad():
            model_output = model(**encoded_input)

        # Perform pooling
        sentence_embeddings = mean_pooling(model_output, encoded_input['attention_mask'])

        # Normalize embeddings
        sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)

        # Return the embeddings as a list of lists of floats
        return sentence_embeddings.tolist()
    except Exception as e:
        print(e)
        raise Exception("Failed to get embeddings from MPNet")
