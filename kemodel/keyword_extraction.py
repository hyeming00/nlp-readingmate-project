from keybert import KeyBERT
import pandas as pd
import re
from transformers import BertModel, AutoModel
from collections import defaultdict
from tqdm import tqdm
import argparse
import os
import torch

from preprocessing import extracts_nouns
from keybert_model import KeywordExtraction
from transformers.pipelines import pipeline
from transformers import AutoModel


if __name__:

    # # 데이터 불러오기
    # print('Loading Data')
    # DATA_DIR = '../../data/기술과학_valid_ver2.csv'
    # train_df = pd.read_csv(DATA_DIR)

    # temp_df = train_df[(train_df['answer_type'] == '절차(방법)형') | (train_df['answer_type'] == '정답경계추출형')| (train_df['answer_type'] == '다지선다형')]
    # temp_df = temp_df[['id', 'context', 'answer_type', 'answer']]
    
    # koquard 데이터 불러오기
    DATA_DIR = '../../data/squad_kor_v1_test_reformatted.csv'
    train_df = pd.read_csv(DATA_DIR)
    temp_df = train_df[['context', 'question', 'answer']]

    # context별로 id 재구성(같은 context -> 같은 id)
    temp_df['id'] = temp_df['context'].astype('category').cat.codes

    # unique한 context 데이터셋 만들기
    temp_dict = defaultdict()
    docs_list = []
    for _, data in tqdm(temp_df.iterrows(), desc='unique한 context 데이터셋 만들기', total = len(temp_df)):
        id = data['id']
        answer = data['answer']
        if id not in temp_dict.keys():
            temp_dict[id] = [answer]
            docs_list.append([id, extracts_nouns(data['context'])])
        else:
            temp_dict[id].append(answer)

    final_dict = defaultdict()
    for id, answer in temp_dict.items():
        final_dict[id] = list(set(answer))
    docs_df = pd.DataFrame(docs_list, columns=['id', 'context'])
    answer_df = pd.DataFrame(list(final_dict.items()), columns = ['id', 'answer'])
    
    # KeyBERT options
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_name', required=False, default='skt/kobert-base-v1', help='모델 이름')
    parser.add_argument('--num_to_gen', required=False, type=int, default=3, help='생성할 keyword 수')
    parser.add_argument('--n_gram', required=False, type=int, default=5, help='keyword의 max n gram')
    parser.add_argument('--use_maxsum', required=False, help='다양성 방법1')
    parser.add_argument('--nr_candidates',required=False, type=int, help='use_maxsum=True일 경우 고려할 대상 개수')
    parser.add_argument('--use_mmr', required=False, help='다양성 방법2')
    parser.add_argument('--diversity', required=False, type=float, default=0.8, help='use_mmr=True할 경우 다양성을 얼마나 줄건지(숫자 클수록 다양성 커짐)')
    args = parser.parse_args()
    
    # model = AutoModel.from_pretrained(args.model_name)
    # model = args.model_name
    kw_model = KeyBERT()
    # model = pipeline("feature-extraction", model="args.model_name")
    # kw_model = KeyBERT(model)
    keywords_object = KeywordExtraction(kw_model, 
                                        num_to_gen = args.num_to_gen, 
                                        stop_words = None,
                                        use_maxsum=args.use_maxsum, 
                                        nr_candidates=args.nr_candidates,
                                        use_mmr=args.use_mmr,
                                        diversity=args.diversity)
    
    # 키워드 추출
    new_data = []
    for _, data in tqdm(docs_df.iterrows(), desc='keyword extraction', total = len(docs_df)):
        id = data['id']
        context = data['context']
        keyword = set()
        for i in range(1, args.n_gram+1):            
            keywords_candidates = keywords_object.generate_keywords(context, i)
            keyword.update(keywords_candidates)
        new_data.append([id, context, keyword])
    keyword_df = pd.DataFrame(new_data, columns=['id', 'context', 'keyword'])
    
    score = 0   # 점수 계산
    if_keyword_exist = 0    # keyword가 context에 있는지 확인
    total_keyword = 0   # 생성된 keyword 개수
    for _, data in keyword_df.iterrows():
        id = data['id']
        for keyword in tqdm(data['keyword'], total=len(data)):
            total_keyword+=1
            context_str = str(docs_df[docs_df['id']==id]['context'].values[0])
            if keyword in context_str:
                if_keyword_exist += 1
            if keyword in answer_df[answer_df['id']==id]['answer'].tolist()[0]:
                score += 1

    score_rate = '{:.4f}'.format(score/total_keyword)
    if_keyword_exist = '{:.4f}'.format(if_keyword_exist/total_keyword)
    score_dict = {'score':score,
                  'score_rate':score_rate,
                  'if_keyword_exist':if_keyword_exist,
                  'model_name':args.model_name, 
                  'num_to_gen':args.num_to_gen, 
                  'n_gram':args.n_gram, 
                  'use_maxsum':args.use_maxsum, 
                  'nr_candidates':args.nr_candidates, 
                  'use_mmr':args.use_mmr, 
                  'diversity':args.diversity,
                  }
    score_df = pd.DataFrame([score_dict])

    #keyword vs answer 비교 csv파일
    merged_df = pd.merge(keyword_df, answer_df, on='id', how='left')
    only_model = args.model_name.split('/')
    only_model = only_model[1]
    merged_df[['id', 'keyword', 'answer', 'context']].to_csv(os.path.join('keyword_answer', f'{only_model}_{args.num_to_gen}_{args.use_maxsum}_{args.nr_candidates}_{args.use_mmr}_{args.diversity}.csv'), index=False)

    file = 'score.csv'
    if os.path.isfile(file):
        with open(file, 'a') as file_data:
            score_df.to_csv(file, mode='a',index=False, header=False)
    else:
        score_df.to_csv(file, index=False)