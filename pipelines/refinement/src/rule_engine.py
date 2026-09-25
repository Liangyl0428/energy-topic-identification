from refine_common import *
from taxonomy import RULES

class Rule:
    def __init__(self,r,index):
        self.data=r;self.index=index
        self.obj=re.compile(r['object_pattern'],re.I)
        self.task=re.compile(r['task_pattern'],re.I) if r['task_pattern'] else None
        self.exclude=re.compile(r['exclude_title_pattern'],re.I) if r['exclude_title_pattern'] else None
        self.required=re.compile(r['required_text_pattern'],re.I) if r.get('required_text_pattern') else None

    def match(self,title,text):
        if self.exclude and self.exclude.search(title):return 0
        if self.required and not self.required.search(text):return 0
        obj_title=self.obj.search(title)
        task_title=not self.task or self.task.search(title)
        if obj_title and task_title:return 3
        if obj_title and self.task and self.task.search(text):return 2
        if self.obj.search(text) and (not self.task or self.task.search(text)):return 1
        return 0

def compiled():return [Rule(r,i) for i,r in enumerate(RULES)]

def routing_view(title,body,source):
    # Full titles; abstracts usually fit. Long patent/policy annexes are not task definitions.
    limit=4000 if source=='policy' else 16000
    return title+' . '+body[:limit], min(len(body),limit)
