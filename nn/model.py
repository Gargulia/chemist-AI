# -*- coding: utf8 -*-
# Имя: model.py
# Месторасположение файла: ProjectRoot/nn/
# Автор скрипта: Gargulia
# Описание скрипта:
#       Полный алгоритм получения рекомендаций.

import random
import sqlite3
import time
from web.db import searching_popular_good_by_generic
import gensim
from scipy.spatial.distance import cosine

start_time = time.time()
path_to_model = 'nn/models/trained_nn1.model' # путь к тренироавнной модели 
model = gensim.models.Word2Vec.load(path_to_model)
conn = sqlite3.connect("web/cluster.db", check_same_thread=False) # подключение к базе товар-кластер


def get_generics_recommndation(cheque):
    cursor = conn.cursor()

    # словарь кластер -> дженерики => кластер -> векоторы.
    def gen_to_vector(dict):
        clust_array = []
        d = {}
        for i in dict:
            for j in dict[i]:
                clust_array.append(list(model.wv.word_vec(j)))
            d[i] = clust_array
            clust_array = []
        return d  

    # усредняет поданные на вход векторы в виде списка списков(списка векторов)
    def middleVector(args):
        mas = []
        for x in range(len(args[0])):
            mas.append(0)
        for vector in args:
            for x in range(len(vector)):
                mas[x] = mas[x] + vector[x]
        for x in range(len(mas)):
            mas[x] = mas[x] / len(args)
        return mas

    # Получение дженериков заданного кластера кроме тех, что уже в чеке.
    def searching_recommendation(clusterNum, generic_arr):
        sql = f"SELECT generic FROM generic_cluster WHERE cluster = '" + \
            str(clusterNum) + \
            f"' AND generic NOT IN ({','.join(['?']*len(generic_arr))})"
        cluster = cursor.execute(sql, generic_arr).fetchall()
        return [gen[0] for gen in cluster]

    # получаем словарь кластер->векторы
    vectors = gen_to_vector(cheque)
    # усредняем векторы по каждому кластеру(vectors теперь словарь кластер->вектор)
    for i in vectors:
        vectors[i] = middleVector(vectors[i])
    # Получаем дженерики того же кластера для каждого кластера в словарь generic_rec
    generics_rec = {}
    for i in cheque:
        generics_rec[i] = searching_recommendation(i, cheque[i])

    # В similarity_dict получаем структуру вида {cluster: [(generic, distance), (generic, distance)...], ...}
    # Где вычисляется косинусное расстояние между усредненным вектором покупок из одного кластера с дженериками из того же кластера
    similarity_dict = {}
    for i in vectors:
        similarity_temp = {}
        for j in generics_rec[i]:
            similarity_temp[j] = cosine(vectors[i], model.wv.get_vector(j))
        similarity_dict[i] = sorted(similarity_temp.items(), key=lambda x: x[1])
        pass

    # В случае если на кластер нет рекомендаций - удаляем его
    def get_rid_of_none(similarity_dict):
        similarity_temp = similarity_dict
        similarity_dict = {}
        for i in similarity_temp:
            if not similarity_temp[i] == []:
                similarity_dict[i] = similarity_temp[i]
        return similarity_dict

    
    similarity_dict = get_rid_of_none(similarity_dict)
    recomendating_gens = []
    for _ in range(5):
        # Если нет рекомендация ни для одного кластера - break
        if len(similarity_dict) == 0:
            break
        # Выбор рандомного кластера из списка с косинусным расстоянием
        cluster = random.randint(0, len(similarity_dict)-1)
        keys = list(similarity_dict.keys()) # Список ключей словаря с косинусным расстоянием
        recomendating_gens.append(similarity_dict[keys[cluster]][0][0]) # В конечный список рекомендаций добавляем дженерик и...
        similarity_dict[keys[cluster]]=similarity_dict[keys[cluster]][1:] # Удаляем дженерик из списка словаря с косинусным расстоянием 
        similarity_dict = get_rid_of_none(similarity_dict) # чистим словарь от пустых рекомендаций

    # Если рекомендаций менее 5, но больше 0, то добираем необходимое кол-во самых похожих на первый дженерик.     
    if len(recomendating_gens) > 0 and len(recomendating_gens)<5:
        additional = [i[0] for i in model.most_similar(recomendating_gens[0])[:5-len(recomendating_gens)]]
        recomendating_gens = recomendating_gens+additional


    # Если рекомендаций нет(редчайший случай), то берем пять самых похожих на первый товар из корзины
    if len(recomendating_gens) == 0:
        recomendating_gens = [i[0] for i in model.most_similar(list(cheque.items())[0][1][0])[:5]]
    
    return recomendating_gens


def get_recs_from_gens(generics):
    recs = []
    for g in generics:
        temp = searching_popular_good_by_generic(g)
        recs.append(temp)
    return recs
