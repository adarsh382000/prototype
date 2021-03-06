import os
from tensorflow import keras
import mtcnn
import cv2
import numpy as np
import random
from sklearn.preprocessing import Normalizer
from scipy.spatial.distance import cosine
from pymongo import MongoClient
import pymongo
import streamlit as st
import gdown
from git import Repo
import SessionState

os.system('apt-get update && apt-get install -y cmake')

def data():
    try:
       client = MongoClient(st.secrets['db_address'])
       db = client['Attendence']
       return db
    except Exception:
       st.write("Error connecting to the Database")
       st.stop()

db = data()
train_model = st.secrets['train_model']

#@st.cache(suppress_st_warning=True)
def face_recognition_model():
    try:
        gdown.download(train_model, 'model.h5', quiet=False)
        model = keras.models.load_model('model.h5')
        return model
    except Exception:
        st.write("Error loading predictive model")
        st.stop()

model = face_recognition_model()

if not os.path.exists('/app/prototype/MaskTheFace/'):
   Repo.clone_from('https://github.com/aqeelanwar/MaskTheFace.git','/app/prototype/MaskTheFace')
os.chdir('/app/prototype/MaskTheFace')

def detect_face(ad):
  detector = mtcnn.MTCNN()
  return detector.detect_faces(ad)

def get_emb(face):
  face = normalize(face)
  face = cv2.resize(face,(160,160))
  return model.predict(np.expand_dims(face, axis=0))[0]

def normalize(img):
    mean, std = img.mean(), img.std()
    return (img - mean) / std

def get_face(img, box):
    x1, y1, width, height = box
    x1, y1 = abs(x1), abs(y1)
    x2, y2 = x1 + width, y1 + height
    face = img[y1:y2, x1:x2]
    return face, (x1, y1), (x2, y2)

def face(img):
  l2 = Normalizer()
  img = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
  res = detect_face(img)
  if res:
      res = max(res, key = lambda b: b['box'][2] *b['box'][3])
      img, _, _ = get_face(img,res['box'])
      enc = get_emb(img)
      enc = l2.transform(enc.reshape(1,-1))[0]
      enc = enc.tolist()
      return enc
  else:
    return -1

def facemask(img):
    l2 = Normalizer()
    img = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    enc = get_emb(img)
    enc = l2.transform(enc.reshape(1,-1))[0]
    enc = enc.tolist()
    return enc

def masktheface(img):
  cv2.imwrite('no_mask.jpg',img)
  os.system('python mask_the_face.py --path /content/no_mask.jpg --mask_type "cloth"')
  img = cv2.imread('no_mask_cloth.jpg')
  return img

def add_new_person(name,img):
  l2 = Normalizer()
  img = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
  mimg = masktheface(img)
  enc = face(img)
  if enc == -1:
    return -1
  enc_mask = facemask(mimg)
  db.embd.insert_one({'Name' : name, 'embedding' : enc})
  db.embdmask.insert_one({'Name' : name, 'embedding' : enc_mask})
  return 0

def test_person_nomask(img):
  enc = face(img)
  if enc == -1:
    return -1
  cursor = db.embd.find()
  li = list(cursor)
  dist = 1000000.0
  name = "unknown"
  dic = {}
  if len(li) > 0:
    for i in li:
      encdatabase = i['embedding']
      encdatabase = np.array(encdatabase)
      d = cosine(enc,encdatabase)
      dic[i['Name']] = d 
      if d < 0.5 and d < dist:
        name = i['Name']
        dist = d
    return dic
  else:
    return -2

def test_person_mask(img):
  enc = facemask(img)
  cursor = db.embdmask.find()
  li = list(cursor)
  dist = 1000000.0
  name = "unknown"
  dic = {}
  if len(li) > 0:
    for i in li:
      encdatabase = i['embedding']
      encdatabase = np.array(encdatabase)
      d = cosine(enc,encdatabase)
      dic[i['Name']] = d 
      if d < 0.5 and d < dist:
        name = i['Name']
        dist = d
    return dic
  else:
    return -1

def main():
  st.title("Face Recognition Based Attendence System Prototype")

  activities = ["Mark Attendence", "Admin Login", "Admin Registeration"]
  choice = st.sidebar.selectbox("Menu", activities)

  if choice == "Mark Attendence":
    st.write("**Please use image with frontal angle and image should be well lit**")
    st.write("Example image:")
    st.image('/app/prototype/Image.jpg',use_column_width = 'auto')
    uploaded_file = st.file_uploader("Upload image", type=['jpeg', 'png', 'jpg', 'webp'])
    
    if uploaded_file is not None:
     file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
     image = cv2.imdecode(file_bytes, 1)
     if st.button("Proceed"):
         res = test_person_nomask(image)
         if type(res) == dict:
           #st.write("Attendence Marked of: ")
           tot = max(res.values()) + 0.10
           for i,j in res.items():
                st.write("------------------------------------------------------------------------------")
                st.write("Name: " + i)
                st.write("Distance(lower is better): " + str(j))
                st.write("Similarity(higher is better): ")
                my_bar = st.progress(0)
                my_bar.progress(1-(j/tot))
         elif res == -1:
           st.write("No face found, try another image")
         else:
           st.write("Database empty")
         
         st.write("------------------------------------------------------------------------------")
         str.write("Masked Dataset")
         st.write("------------------------------------------------------------------------------")
                 
         res_mask = test_person_mask(image)
         if type(res_mask) == dict:
               #st.write("Attendence Marked of: ")
               tot = max(res_mask.values()) + 0.10
               for i,j in res_mask.items():
                    st.write("------------------------------------------------------------------------------")
                    st.write("Name: " + i)
                    st.write("Distance(lower is better): " + str(j))
                    st.write("Similarity(higher is better): ")
                    my_bar = st.progress(0)
                    my_bar.progress(1-(j/tot))
         else:
               st.write("Database empty")
    else:
     st.write("Please select an image")
     st.stop()
        


  elif choice == "Admin Login":
    st.session_state.useridss = ''
    st.session_state.passwordss = ''
    session_state = SessionState.get(checkboxed=False)
    st.write("**Enter the Credentials to login**")
    form = st.form(key='login')
    userid = form.text_input("UserID(Case-sensitive):", value = st.session_state.useridss)
    password = form.text_input("Password:", type="password", value = st.session_state.passwordss)
    
    if form.form_submit_button("Login") or session_state.checkboxed:
        cursor = db.Admins.find({'_id' : userid})
        li = list(cursor)
        for i in li:
            pas = i['password']
        if len(li) > 0:
            if pas == password:
                session_state.checkboxed = True
                st.session_state.useridss = userid
                st.session_state.passwordss = password
                #session_state2 = SessionState.get(checkboxed=False)
                option = st.selectbox("Select admin operation: ",('Select','Show database','Insert record','Delete record'))
                if option == 'Show database':
                    cursor = db.embd.find()
                    li = list(cursor)
                    if len(li) < 1:
                        st.write("Empty Database")
                        st.stop()
                    else:
                        st.write("**Database:**")
                        k = 1
                        for i in li:
                            st.write(str(k) + '. ' + i['Name'])
                            k+=1
                elif option == 'Insert record':
                    name = st.text_input("Enter the person's name to insert: ")
                    st.write("Upload the Image of Person to Register them in Database")
                    st.write("Example image: ")
                    st.image('/app/prototype/Image.jpg',use_column_width = 'auto')
                    uploaded_file = st.file_uploader("Upload image", type=['jpeg', 'png', 'jpg', 'webp'])
                    if uploaded_file is not None:
                        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
                        image = cv2.imdecode(file_bytes, 1)
                        if st.button("Upload"):
                            res = add_new_person(name,image)
                            if res == 0:
                                st.write("Successfully Registered")
                            else:
                                st.write("No face found, try another image")
                    else:
                        st.write("Upload image")
                elif option == 'Delete record':
                    name = st.text_input("Enter the person's name to delete: ")
                    if st.button("Delete"):
                        res = db.embd.delete_one({'Name' : name})
                        if res.deleted_count == 1:
                            st.write("Succesfully deleted")
                        else:
                            st.write("Record not found")
                elif option == 'Select':
                    st.write("Please select")
                    
            else:
                st.write("Wrong Password!, try again")
        else:
            st.write('Enter valid username, or register a new one')
    
  elif choice == "Admin Registeration":
    st.write("**Enter the Credentials to register as an Admin**")
    form = st.form(key='reg')
    userid = form.text_input("UserID(Case-sensitive):")
    password = form.text_input("Password:", type="password")

    if form.form_submit_button("Proceed"):
        if len(userid) == 0 or len(password) == 0:
            st.write("Please enter valid credentials")
            st.stop()
        try:
            db.Admins.insert_one({'_id' : userid, 'password' : password})
            st.write("Successfully Registered")
        except Exception:
            st.write("UserID already Exists")

if __name__ == "__main__":
    main()
