from keybert import KeyBERT
import pandas as pd
import re
from transformers import BertModel
from collections import defaultdict

def keyword_extraction(context, kw_model, num_to_gen = 5, stop_words = None, n_gram = 5, use_maxsum=True, nr_candidates=10):
    
    keywords = kw_model.extract_keywords(context, 
                                      keyphrase_ngram_range=(1, n_gram), 
                                      stop_words=stop_words, 
                                      top_n=num_to_gen)
    keywords = [k[0] for k in keywords]

    return keywords

def remove_tag(context):
    '''
    html tag 제거, 공백 하나로 대체
    '''
    temp_context = re.sub(r'<[^>]+>', ' ', context)
    final_context = re.sub(r'\s+', ' ', temp_context)
    return final_context