"""Training side of Ghost Agent: pull consented records from the VPS, curate, fine-tune.

Consent is re-checked here (validate.py) as the second line of defence after the
ingestion API: any record without consent.project_opted_in == true is dropped before it
can reach a training set, whatever the server said.
"""

TRIGGER_TOKEN = "ghoststyle"
