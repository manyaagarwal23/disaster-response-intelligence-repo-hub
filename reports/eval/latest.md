# Retrieval evaluation — 2026-10-07 17:34

33 questions, top 10, Ushahidi `78f81b4b`, LLM `qwen/qwen3.8-27b` (not used)

| system | MRR@10 | Hit@1 | Hit@3 | Hit@5 |
|---|---|---|---|---|
| semantic | 0.587 | 48.5% | 63.6% | 72.7% |
| hybrid | 0.605 | 51.5% | 60.6% | 75.8% |

Latency per question: mean 0.2 s, max 0.2 s (target from the brief: under 60 s).

## Per question (rank of first correct file; `-` = not in top 10)

| # | semantic | hybrid | question |
|---|---|---|---|
| 1 | 1 | 1 | Where is the EntityExists contract defined? |
| 2 | 1 | 1 | What does EntityExists::exists() define? |
| 3 | 1 | 1 | Where is verifyEntityLoaded declared abstract and where is it implemented? |
| 4 | 6 | 1 | What exception is thrown when an entity cannot be found? |
| 5 | 4 | 1 | How does the system verify that an entity was actually loaded? |
| 6 | 1 | 2 | Which repository method is used to load an entity before verification? |
| 7 | 3 | 1 | Where is the actual implementation of verifyEntityLoaded? |
| 8 | 3 | 8 | Which use cases call verifyEntityLoaded? |
| 9 | 1 | 1 | Show me how the EntityExists interface is structured. |
| 10 | 1 | 5 | What happens if the exists() method returns false? |
| 11 | 1 | 1 | What happens after an entity is loaded in UpdateUsecase? |
| 12 | 3 | 1 | Where is verifyEntityLoaded implemented and which parts of the system call it? |
| 13 | 1 | 1 | Show me the code for the UpdateUsecase class. |
| 14 | 1 | 1 | What dependencies are injected into the UpdateUsecase? |
| 15 | 1 | 1 | How does the CreateSetPost usecase work? |
| 16 | 6 | 6 | Show me how a post is updated in the system. |
| 17 | 1 | 1 | What methods does the PostRepository provide? |
| 18 | 4 | 5 | How does the system handle fetching entities from the database? |
| 19 | 1 | 1 | Which classes implement the EntityExists contract? |
| 20 | 6 | 1 | Explain what the ReadUsecase does. |
| 21 | 4 | 5 | How does the system prevent an unauthorized user from creating a post? |
| 22 | 1 | 2 | Where is the user's role checked when creating a post? |
| 23 | - | - | Where is the permission to create a post checked? |
| 24 | 1 | - | How does the system determine which roles can create posts? |
| 25 | - | 10 | How does the system check whether a user has Manage Posts permission? |
| 26 | 8 | 7 | Show me the code that validates user permissions. |
| 27 | 1 | 4 | How does the API prevent unauthorized access to usecases? |
| 28 | - | - | What happens when a user without permissions tries to update a post? |
| 29 | 2 | 4 | Explain how roles are assigned to users in the system. |
| 30 | - | - | How does the system validate input data before creating a post? |
| 31 | 1 | 1 | Where is an incoming SMS report parsed? |
| 32 | 2 | 1 | Where is the map pin / post location logic? |
| 33 | - | 3 | Where are the V5 API routes for posts defined? |
