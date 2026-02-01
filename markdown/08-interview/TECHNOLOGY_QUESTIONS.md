# Technology & LLM Development Interview Questions

Questions for candidates working with LLM, Python, and similar projects.

---

## 1. Python Fundamentals

### Core Concepts
1. **Explain the difference between `is` and `==` in Python.**
2. **What are Python decorators and how do they work?**
3. **Explain the Global Interpreter Lock (GIL) and its implications.**
4. **What is the difference between `*args` and `**kwargs`?**
5. **How does Python's garbage collection work?**

### Advanced Python
6. **What are context managers and when would you use them?**
7. **Explain generators and their memory benefits.**
8. **What is the difference between `@staticmethod` and `@classmethod`?**
9. **How do you handle circular imports?**
10. **What are metaclasses and when would you use them?**

### Async Programming
11. **Explain `async/await` in Python.**
12. **What is the difference between threading, multiprocessing, and asyncio?**
13. **When would you use threads vs processes for I/O-bound tasks?**
14. **What is an event loop?**
15. **How do you handle blocking I/O in async code?**

---

## 2. FastAPI Framework

### Basics
16. **What makes FastAPI different from Flask?**
17. **Explain dependency injection in FastAPI.**
18. **How does FastAPI handle request validation?**
19. **What is the role of Pydantic in FastAPI?**
20. **How do you define path parameters vs query parameters?**

### Advanced
21. **How do you handle background tasks in FastAPI?**
22. **Explain middleware in FastAPI.**
23. **How do you implement authentication in FastAPI?**
24. **What is CORS and how do you configure it?**
25. **How do you handle file uploads in FastAPI?**

### Performance
26. **How would you optimize a slow FastAPI endpoint?**
27. **What is uvicorn and how does it relate to FastAPI?**
28. **How do you implement rate limiting?**
29. **What caching strategies work with FastAPI?**
30. **How do you profile FastAPI applications?**

---

## 3. React & Frontend

### Core Concepts
31. **Explain the Virtual DOM in React.**
32. **What is the difference between state and props?**
33. **Explain the React component lifecycle.**
34. **What are React Hooks and why were they introduced?**
35. **What is the purpose of `useRef`?**

### State Management
36. **When would you use `useState` vs `useReducer`?**
37. **How do you manage global state in React?**
38. **What is prop drilling and how do you avoid it?**
39. **Explain Context API vs Redux.**
40. **How do you handle async operations in React?**

### Practical
41. **How do you handle form submissions in React?**
42. **What is the AbortController and when would you use it?**
43. **How do you implement polling in React?**
44. **How do you handle errors in React components?**
45. **What are controlled vs uncontrolled components?**

---

## 4. Large Language Models (LLMs)

### Fundamentals
46. **What is a Large Language Model?**
47. **Explain the difference between GPT, BERT, and LLaMA architectures.**
48. **What is tokenization and why does it matter?**
49. **What are embeddings and how are they created?**
50. **Explain the concept of attention in transformers.**

### Prompting
51. **What is prompt engineering?**
52. **Explain zero-shot vs few-shot prompting.**
53. **What is chain-of-thought prompting?**
54. **How do you structure prompts for JSON output?**
55. **What are common prompt injection attacks and how do you prevent them?**

### Local LLMs
56. **What is Ollama and how does it work?**
57. **Compare Ollama vs LM Studio vs llama.cpp.**
58. **What factors affect local LLM performance?**
59. **How do you choose the right model size for your hardware?**
60. **What is quantization and why is it important for local LLMs?**

### Integration
61. **How do you handle LLM timeout issues?**
62. **What strategies exist for handling malformed LLM output?**
63. **How do you validate LLM responses programmatically?**
64. **What is structured output generation?**
65. **How do you handle rate limiting with LLM APIs?**

---

## 5. RAG (Retrieval-Augmented Generation)

### Concepts
66. **What is RAG and why is it useful?**
67. **Explain the difference between RAG and fine-tuning.**
68. **What are vector databases?**
69. **How do you measure retrieval quality?**
70. **What is semantic search?**

### Implementation
71. **What is FAISS and how does it work?**
72. **Compare FAISS vs Chroma vs Pinecone.**
73. **How do you chunk documents for embedding?**
74. **What chunking strategies exist (fixed, semantic, recursive)?**
75. **How do you handle overlapping chunks?**

### Embeddings
76. **What embedding models are commonly used?**
77. **How do you choose embedding dimensions?**
78. **What is the trade-off between embedding quality and speed?**
79. **How do you update embeddings when documents change?**
80. **What is hybrid search (keyword + semantic)?**

---

## 6. Database Technologies

### PostgreSQL
81. **What are the advantages of PostgreSQL over MySQL?**
82. **Explain ACID properties.**
83. **What are PostgreSQL ARRAY types and when to use them?**
84. **How do you optimize slow queries?**
85. **What is connection pooling?**

### MongoDB
86. **When would you choose MongoDB over PostgreSQL?**
87. **What is GridFS and when should you use it?**
88. **Explain document vs relational data modeling.**
89. **How does MongoDB handle transactions?**
90. **What is sharding in MongoDB?**

### SQLAlchemy
91. **What is an ORM and what are its benefits?**
92. **Explain the difference between Session and Connection.**
93. **How do you handle database migrations?**
94. **What is lazy loading vs eager loading?**
95. **How do you prevent N+1 query problems?**

---

## 7. PDF Processing

### Text Extraction
96. **How does pdfplumber differ from PyPDF2?**
97. **What challenges exist in PDF text extraction?**
98. **When would you need OCR for PDFs?**
99. **How does pytesseract work?**
100. **What is the trade-off between extraction accuracy and speed?**

### Document Processing
101. **How do you handle multi-column PDFs?**
102. **What about scanned documents vs native PDFs?**
103. **How do you extract tables from PDFs?**
104. **What is document layout analysis?**
105. **How do you handle password-protected PDFs?**

---

## 8. Data Validation & Pydantic

### Basics
106. **What is Pydantic and why use it?**
107. **How do field validators work?**
108. **What is the difference between `mode='before'` and `mode='after'`?**
109. **How do you define optional fields?**
110. **What are computed fields?**

### Advanced
111. **How do you create custom validators?**
112. **What is model inheritance in Pydantic?**
113. **How do you serialize Pydantic models to JSON?**
114. **What are discriminated unions?**
115. **How do you handle dynamic fields?**

---

## 9. API Design & REST

### Principles
116. **What are REST principles?**
117. **Explain idempotency in HTTP methods.**
118. **How do you design error responses?**
119. **What is API versioning and strategies for it?**
120. **How do you document APIs?**

### Practical
121. **What HTTP status codes should you use and when?**
122. **How do you handle pagination?**
123. **What is the difference between PUT and PATCH?**
124. **How do you implement search/filter endpoints?**
125. **What about file upload API design?**

---

## 10. Testing & Quality

### Unit Testing
126. **What is pytest and how does it work?**
127. **How do you mock external dependencies?**
128. **What is test coverage and is 100% always good?**
129. **How do you test async code?**
130. **What are fixtures in pytest?**

### Integration Testing
131. **How do you test API endpoints?**
132. **What is TestClient in FastAPI?**
133. **How do you test database interactions?**
134. **What about testing LLM integrations?**
135. **How do you handle flaky tests?**

---

## 11. DevOps & Deployment

### Containerization
136. **What is Docker and why use it?**
137. **How do you write a Dockerfile for Python apps?**
138. **What is docker-compose?**
139. **How do you handle environment variables in Docker?**
140. **What are multi-stage builds?**

### CI/CD
141. **What is CI/CD?**
142. **How do you set up GitHub Actions for Python?**
143. **What should be in a pre-commit hook?**
144. **How do you handle secrets in CI/CD?**
145. **What is blue-green deployment?**

---

## 12. System Design

### Scalability
146. **How would you design a system for 10,000 concurrent users?**
147. **What is horizontal vs vertical scaling?**
148. **How do you implement load balancing?**
149. **What is a message queue and when to use it?**
150. **How do you handle database bottlenecks?**

### Architecture
151. **What is microservices vs monolithic architecture?**
152. **When would you split a monolith?**
153. **What is event-driven architecture?**
154. **How do you handle distributed transactions?**
155. **What is eventual consistency?**

---

## 13. Security

### Web Security
156. **What is SQL injection and how to prevent it?**
157. **What is XSS and mitigation strategies?**
158. **How do you secure file uploads?**
159. **What is CSRF protection?**
160. **How do you implement rate limiting?**

### Authentication
161. **What is JWT and how does it work?**
162. **Explain OAuth 2.0 flow.**
163. **What is the difference between authentication and authorization?**
164. **How do you store passwords securely?**
165. **What is RBAC (Role-Based Access Control)?**

---

## 14. Debugging & Troubleshooting

### Techniques
166. **How do you debug a production issue?**
167. **What logging best practices do you follow?**
168. **How do you profile Python code?**
169. **What is a memory leak and how to detect it?**
170. **How do you handle race conditions?**

### Tools
171. **What debugging tools do you use?**
172. **How do you use Python's pdb?**
173. **What is structured logging?**
174. **How do you analyze slow database queries?**
175. **What APM tools have you used?**

---

## 15. LLM-Specific Challenges

### Reliability
176. **How do you handle LLM hallucinations?**
177. **What is grounding in LLM responses?**
178. **How do you implement fallback when LLM fails?**
179. **What retry strategies work for LLM APIs?**
180. **How do you validate extracted data accuracy?**

### Performance
181. **How do you reduce LLM latency?**
182. **What is streaming in LLM responses?**
183. **How do you cache LLM responses?**
184. **What is batching in LLM inference?**
185. **How do you handle long context windows?**

### Cost
186. **How do you estimate LLM API costs?**
187. **What strategies reduce token usage?**
188. **When to use smaller vs larger models?**
189. **What is prompt caching?**
190. **How do you implement usage quotas?**

---

## 16. Project Management

### Development Process
191. **How do you estimate development tasks?**
192. **What is your approach to code reviews?**
193. **How do you handle technical debt?**
194. **What documentation do you maintain?**
195. **How do you prioritize features vs bugs?**

### Collaboration
196. **How do you work with non-technical stakeholders?**
197. **What's your approach to requirements gathering?**
198. **How do you handle scope creep?**
199. **What version control workflow do you prefer?**
200. **How do you onboard team members?**

---

*Last updated: February 1, 2026*
