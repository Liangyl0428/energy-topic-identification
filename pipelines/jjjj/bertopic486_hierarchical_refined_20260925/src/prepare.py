from refine_common import *

def main():
    topics=pd.read_csv(OLD/'results/merged_topics.csv').fillna('')
    flow=pd.read_csv(NEW/'results/old486_to_new1000.csv')
    cards=read(MERGED/'review/topic_cards.json')
    priority=topics[topics.status.isin(['宽泛待细分','混杂待重分'])]
    assert len(topics)==486 and len(priority)==280
    snapshots=[]
    for root in [OLD,NEW,MERGED]:
        snapshots.append(dict(directory=str(root),delivery_manifest_sha256=sha(root/'DELIVERY_MANIFEST.json')))
    dump(BASE/'INPUT_SNAPSHOT.json',dict(created_utc=now(),inputs=snapshots,documents=5119004,
        priority_parents=280,priority_documents=int(priority.documents.sum()),
        method='486 parents retained; 1000 classes are candidate evidence, not automatic child labels; per-record quality and object/task gates with abstention'))
    packets=[]
    for r in topics.itertuples():
        f=flow[(flow.old_topic_id==r.merged_topic_id)&(flow.documents>=50)&(flow.share_of_old>=.05)].sort_values('documents',ascending=False)
        candidates=[]
        for c in f.itertuples():
            card=cards[int(c.new_topic_id[1:])]
            candidates.append(dict(raw1000=c.new_topic_id,documents=int(c.documents),share_of_parent=c.share_of_old,
                keywords=card['keywords'],center=card['samples'].get('center:1'),random=card['samples'].get('random:1')))
        packets.append(dict(parent_id=r.merged_topic_id,name=r.name,status=r.status,documents=int(r.documents),
            priority=r.status in ['宽泛待细分','混杂待重分'],candidates=candidates))
    dump(BASE/'review/parent_candidate_packets.json',packets)
    topics.to_csv(BASE/'results/main_directory_486.csv',index=False,encoding='utf-8-sig')
    progress('inputs_and_all_486_candidate_packets_ready',priority_parents=280,priority_documents=int(priority.documents.sum()))

if __name__=='__main__':main()
