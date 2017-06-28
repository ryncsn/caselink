A webservice to manage linkage between autotest cases, manual test cases, and bugs, powered by Django.

Install Requirement:
pip install -r requirement.txt

Run Migrate:
./manager.py migrate

Run Dev Server:
./manage.py runserver 0.0.0.0:8888

Load initial data:
./manage.py loaddata ./caselink/fixtures/initial\_data.yaml

Load baseline data:
./manage.py loaddata ./caselink/fixtures/baseline.yaml

Run celery worker:
celery worker -A caselink -n localhost -l info
