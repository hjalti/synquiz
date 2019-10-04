Synquiz - The Pubquiz Overengineered
====================================

Setup
-----

To initialize the setup

```
git clone https://github.com/hjalti/synquiz.git
cd synquiz
./setup.sh
pipenv install
```


Making a quiz
-------------

```
# Initialize a quiz
python quiz.py init my_quiz

# Start a watcher and server
python quiz.py watch my_quiz
```

Now you can open `my_quiz/quiz.yaml` and open aim your browser at
http://localhost:8000. When the file is edited, the quiz slide show will
automatically update.
