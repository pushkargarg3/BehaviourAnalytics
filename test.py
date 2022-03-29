from rest_framework.parsers import JSONParser
from django.http import JsonResponse
from app import models
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import json
from django.conf import settings
import requests
import urllib.request
import time
import os
import difflib
from difflib import SequenceMatcher
import pdb
from nltk.tokenize import LineTokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

base_url = settings.MEDIA_ROOT
tk = LineTokenizer()

@csrf_exempt
def base(request):
    return render(request,'index.html')

@csrf_exempt
def result(request):
    return render(request,'result.html')

def downloadFile(file,filename,sha):
    if os.path.exists(os.path.join(base_url,sha)):
        fileDirectory = os.path.join(base_url,sha,filename)
    else:
        os.makedirs(os.path.join(base_url,sha))
        fileDirectory = os.path.join(base_url,sha,filename)
    urllib.request.urlretrieve(file,fileDirectory)
    return fileDirectory


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

@api_view(['POST'])
def getRepos(request):
    if request.method == 'POST':
        data = JSONParser().parse(request)
        if not data:
            return Response({'message':'No Data Received'}, status=status.HTTP_400_BAD_REQUEST)
        userName = data.get('user_name')
        req = requests.get(f'https://api.github.com/users/{userName}/repos')
        if req.status_code == 200:
            res = req.json()
            finalData = []
            for singleRes in res:
                finalData.append(singleRes.get('name'))
            return Response({'data':finalData},status=status.HTTP_200_OK)
        
@api_view(['POST'])
def getbranches(request):
    if request.method == 'POST':
        data = JSONParser().parse(request)
        if not data:
            return Response({'message':'No Data Received'}, status=status.HTTP_400_BAD_REQUEST)
        userName = data.get('user_name')
        repoName = data.get('repo_name')
        req = requests.get(f'https://api.github.com/repos/{userName}/{repoName}/branches')
        if req.status_code == 200:
            res = req.json()
            finalData = []
            for singleRes in res:
                finalData.append(singleRes.get('name'))
            return Response({'data':finalData},status=status.HTTP_200_OK)

def vectorize(Text): return TfidfVectorizer().fit_transform(Text).toarray()
def similarity(doc1, doc2): return cosine_similarity([doc1, doc2])

def check_plagiarism(s_vectors,plagiarism_results):
    for student_a, text_vector_a in s_vectors:
        new_vectors = s_vectors.copy()
        current_index = new_vectors.index((student_a, text_vector_a))
        del new_vectors[current_index]
        for student_b, text_vector_b in new_vectors:
            sim_score = similarity(text_vector_a, text_vector_b)[0][1]
            student_pair = sorted((student_a, student_b))
            score = (student_pair[0], student_pair[1], sim_score)
            plagiarism_results.add(score)
    return sim_score
    # return plagiarism_results

@api_view(['POST'])
def getData(request):
    if request.method == 'POST':
        data = JSONParser().parse(request)
        if not data:
            return Response({'message':'No Data Received'}, status=status.HTTP_400_BAD_REQUEST)
        userName = data.get('user_name')
        repoName = data.get('repo_name')
        branchName = data.get('branch_name')
        req = requests.get(f'https://api.github.com/repos/{userName}/{repoName}/branches/{branchName}')
        if req.status_code == 200:
            res = req.json()
            commitData = res.get('commit')
            childSha = commitData.get('sha')
            reqData = requests.get(f'https://api.github.com/repos/{userName}/{repoName}/commits/{childSha}')
            if reqData.status_code == 200:
                resData = reqData.json().get('files')
                allFilesData = []
                fileNames = []
                for singleres in resData:
                    patchData = singleres.get('patch')
                    print(patchData)
                    finalLines = tk.tokenize(patchData)
                    newList = []
                    oldList = []
                    for singleline in finalLines[1:]:
                        if '-' == singleline[0]:
                            oldList.append(singleline[1:])
                        elif '+' == singleline[0]:
                            newList.append(singleline[1:])
                    send_data = []
                    new_data = []
                    if (newList and oldList):
                        if len(newList) > len(oldList):
                            count = len(newList) - len(oldList)
                            print(count)
                            for i in range(len(oldList)):
                                splitedNew = newList[i].split('=')
                                splitedOld = oldList[i].split('=')
                                if len(splitedNew) > 1 and len(splitedOld) > 1:
                                    ratio = similar(splitedNew[-1],splitedOld[-1])
                                    if ratio == 1:
                                        newratio = similar(splitedNew[0],splitedOld[0])
                                        if newratio == 1:
                                            comment = "Nothing Changed"
                                            send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                            new_data.append({"line": newList[i],"type": 'same',"line_no": ''})
                                        else:
                                            comment = "only variable has changed"
                                            send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                            new_data.append({"line": oldList[i],"type": 'var_changed',"line_no": ''})
                                            new_data.append({"line": newList[i],"type": 'var_changed',"line_no": ''})
                                    else:
                                        comment = "line chaned"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": oldList[i],"type": 'minus',"line_no": ''})
                                        new_data.append({"line": newList[i],"type": 'plus',"line_no": ''})
                                else:
                                    ratio = similar(newList[i],oldList[i])
                                    if ratio == 1:
                                        comment = "Nothing Changed"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": newList[i],"type": 'same',"line_no": ''})
                                    else:
                                        comment = "line chaned"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": oldList[i],"type": 'minus',"line_no": ''})
                                        new_data.append({"line": newList[i],"type": 'plus',"line_no": ''})
                            for i in newList[-count:]:
                                comment = "line added"
                                send_data.append({'newLine':i,'comment':comment})
                                new_data.append({"line": i,"type": 'plus',"line_no": ''})
                        elif len(oldList) > len(newList):
                            count = len(oldList) - len(newList)
                            print(count)
                            for i in range(len(newList)):
                                splitedNew = newList[i].split('=')
                                splitedOld = oldList[i].split('=')
                                if len(splitedNew) > 1 and len(splitedOld) > 1:
                                    ratio = similar(splitedNew[-1],splitedOld[-1])
                                    if ratio == 1:
                                        newratio = similar(splitedNew[0],splitedOld[0])
                                        if newratio == 1:
                                            comment = "Nothing Changed"
                                            send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                            new_data.append({"line": newList[i],"type": 'same',"line_no": ''})
                                        else:
                                            comment = "only variable has changed"
                                            send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                            new_data.append({"line": oldList[i],"type": 'var_changed',"line_no": ''})
                                            new_data.append({"line": newList[i],"type": 'var_changed',"line_no": ''})
                                    else:
                                        comment = "line chaned"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": oldList[i],"type": 'minus',"line_no": ''})
                                        new_data.append({"line": newList[i],"type": 'plus',"line_no": ''})
                                else:
                                    ratio = similar(newList[i],oldList[i])
                                    if ratio == 1:
                                        comment = "Nothing Changed"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": newList[i],"type": 'same',"line_no": ''})
                                    else:
                                        comment = "line chaned"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": oldList[i],"type": 'minus',"line_no": ''})
                                        new_data.append({"line": newList[i],"type": 'plus',"line_no": ''})
                            for i in oldList[-count:]:
                                comment = "line deleted"
                                send_data.append({'oldLine':i,'comment':comment})
                                new_data.append({"line": i,"type": 'minus',"line_no": ''})
                        else:
                            for i in range(len(oldList)):
                                splitedNew = newList[i].split('=')
                                splitedOld = oldList[i].split('=')
                                if len(splitedNew) > 1 and len(splitedOld) > 1:
                                    ratio = similar(splitedNew[-1],splitedOld[-1])
                                    if ratio == 1:
                                        newratio = similar(splitedNew[0],splitedOld[0])
                                        if newratio == 1:
                                            comment = "Nothing Changed"
                                            send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                            new_data.append({"line": newList[i],"type": 'same',"line_no": ''})
                                        else:
                                            comment = "only variable has changed"
                                            send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                            new_data.append({"line": oldList[i],"type": 'var_changed',"line_no": ''})
                                            new_data.append({"line": newList[i],"type": 'var_changed',"line_no": ''})
                                    else:
                                        comment = "line chaned"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": oldList[i],"type": 'minus',"line_no": ''})
                                        new_data.append({"line": newList[i],"type": 'plus',"line_no": ''})
                                else:
                                    ratio = similar(newList[i],oldList[i])
                                    if ratio == 1:
                                        comment = "Nothing Changed"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": newList[i],"type": 'same',"line_no": ''})
                                    else:
                                        comment = "line chaned"
                                        send_data.append({'newLine':newList[i],'oldLine':oldList[i],'comment':comment})
                                        new_data.append({"line": oldList[i],"type": 'minus',"line_no": ''})
                                        new_data.append({"line": newList[i],"type": 'plus',"line_no": ''})
                    else:
                        if newList:
                            for i in newList:
                                comment = "line added"
                                send_data.append({'newLine':i,'comment':comment})
                                new_data.append({"line": i,"type": 'plus',"line_no": ''})
                        elif oldList:
                            for i in oldList:
                                comment = "line deleted"
                                send_data.append({'oldLine':i,'comment':comment})
                                new_data.append({"line": i,"type": 'minus',"line_no": ''})
                        else:
                            comment = "nothing changed"
                            send_data.append({'comment':comment})
                    checkData = [' '.join(newList),' '.join(oldList)]
                    vectors = vectorize(checkData)
                    s_vectors = list(zip(['newFile','oldFile'], vectors))
                    plagiarism_results = set()
                    checkPlagiarism = check_plagiarism(s_vectors,plagiarism_results)
                    allFilesData.append({"filename": singleres.get('filename'),"status": singleres.get('status'),"additions": singleres.get('additions'),\
                        "deletions": singleres.get('deletions'),"changes": singleres.get('changes'),'plagiarismResult':str(checkPlagiarism),'lines':new_data})
                    fileNames.append(singleres.get('filename'))
                return Response({'files_data':allFilesData,'filenames':fileNames},status=status.HTTP_200_OK)
            else:
                return Response({'data':reqData.json()},status=status.HTTP_200_OK)
        else:
            return Response({'data':req.json()},status=status.HTTP_200_OK)

