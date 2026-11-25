import hashlib
def hash_token(token: str)-> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()



token = "Pq47oj-_nVgV20am01XcoHOujU_fdAjf0jvKMDi3cKxo5F7_e1SLOsh6oTnrJThiKIBZ8dqDQG94pyBu8kBnnA/1/010001a21271ba32-1bbe529f-0020-43ce-ab2d-410d95b7684d-000000/TZICzuN3tudS2jl-7MjzXCmRlYJpK7TSnbItvH0rlww=452"

hash1 = hash_token(token)
hash2 = hash_token(token)

print(hash1)
print(hash2)
print(hash1 == hash2)
