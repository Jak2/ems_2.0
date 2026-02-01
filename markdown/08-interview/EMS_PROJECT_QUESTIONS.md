# EMS 2.0 Project-Specific Interview Questions

These are questions an interviewer might ask about the EMS 2.0 project specifically.

---

## 1. Project Overview & Architecture

### Basic Understanding
1. **What is EMS 2.0 and what problem does it solve?**
2. **Explain the high-level architecture of the system.**
3. **Why did you choose a dual-database approach (PostgreSQL + MongoDB)?**
4. **What is the role of each database in the system?**

### Technical Decisions
5. **Why use FastAPI instead of Flask or Django?**
6. **Why did you choose React for the frontend?**
7. **Why use a local LLM (Ollama) instead of cloud APIs like OpenAI?**
8. **What are the trade-offs of using a local LLM vs cloud LLM?**

---

## 2. CV Upload & Processing Flow

### Upload Mechanism
9. **Walk me through what happens when a user uploads a CV.**
10. **Why do you use background threads instead of async/await for CV processing?**
11. **How does the frontend know when CV processing is complete?**
12. **What is the job polling mechanism and why was it implemented this way?**

### PDF Processing
13. **How do you extract text from PDF files?**
14. **What happens if pdfplumber fails to extract text?**
15. **How does OCR fallback work with pytesseract?**
16. **What challenges did you face with PDF text extraction?**

---

## 3. LLM Integration

### Ollama Integration
17. **How does the system communicate with Ollama?**
18. **Explain the difference between CLI and HTTP API approaches for Ollama.**
19. **What prompt engineering techniques did you use for CV extraction?**
20. **How do you handle cases where the LLM returns malformed JSON?**

### Data Extraction
21. **What fields do you extract from a resume?**
22. **How do you validate the LLM's output?**
23. **What is the role of Pydantic in data extraction?**
24. **How did you handle the issue where LLM returns dicts instead of strings in arrays?**

---

## 4. Database Design

### PostgreSQL
25. **What is the Employee model schema?**
26. **How do you generate unique employee IDs?**
27. **Why store arrays (skills, education) as ARRAY types in PostgreSQL?**
28. **Explain the SQLAlchemy ORM usage in the project.**

### MongoDB
29. **Why use GridFS for PDF storage?**
30. **What is stored in MongoDB vs PostgreSQL?**
31. **How do you retrieve files from GridFS?**
32. **What is the extracted_data collection used for?**

---

## 5. Chat & Query System

### Chat Flow
33. **How does the chat endpoint work?**
34. **How do you maintain conversation context (session memory)?**
35. **What happens when a user asks about a specific employee?**
36. **How does name-based search work in the chat?**

### RAG Implementation
37. **What is RAG and how is it implemented in EMS 2.0?**
38. **Why use FAISS for vector storage?**
39. **How do you chunk text for embedding?**
40. **What embedding model do you use and why?**

---

## 6. CRUD Operations

### Via Chat Interface
41. **How does the LLM understand CRUD intent from natural language?**
42. **How do you update an employee record via chat?**
43. **How do you handle the "delete employee" command?**
44. **What validation happens before CRUD operations?**

### API Endpoints
45. **What REST endpoints does the system expose?**
46. **How do you handle errors in API endpoints?**
47. **What response format do you use for success/failure?**

---

## 7. Frontend Implementation

### React Components
48. **Explain the component structure of the frontend.**
49. **How does the Upload component handle file selection?**
50. **How is state managed between App.jsx and Upload.jsx?**
51. **What is the onNewMessage callback pattern used for?**

### UX Features
52. **How do you show file preview before upload?**
53. **What is the purpose of the AbortController?**
54. **How does the stop button work during processing?**
55. **How do you handle backend unreachability?**

---

## 8. Error Handling & Debugging

### Common Issues
56. **Describe the "variable shadowing" bug you encountered and how you fixed it.**
57. **What was the duplicate employee_id issue and the solution?**
58. **How did you fix Pydantic validation errors with LLM dict outputs?**
59. **What was blocking multiple resume uploads and how was it fixed?**

### Debugging Approach
60. **How do you debug issues in the CV processing pipeline?**
61. **What logging strategy do you use?**
62. **Where are job status files stored and what do they contain?**
63. **How do you trace errors from frontend to backend?**

---

## 9. Performance & Scalability

### Current Implementation
64. **What is the bottleneck in the current system?**
65. **How long does CV processing typically take?**
66. **What limits the number of concurrent uploads?**

### Improvements
67. **How would you scale this system for thousands of CVs?**
68. **Would you use a message queue? Which one and why?**
69. **How would you implement caching?**
70. **What database optimizations would you consider?**

---

## 10. Security Considerations

71. **How do you validate uploaded files?**
72. **What prevents malicious PDF uploads?**
73. **How is the API secured?**
74. **What CORS settings are configured and why?**
75. **How would you add authentication to this system?**

---

## 11. Deployment & DevOps

76. **How would you deploy this application?**
77. **What environment variables are required?**
78. **How do you handle database migrations?**
79. **What monitoring would you add?**
80. **How would you containerize this application?**

---

## 12. Code Quality & Best Practices

81. **How is the codebase organized?**
82. **What design patterns are used?**
83. **How do you handle configuration?**
84. **What testing strategy would you implement?**
85. **How would you document API endpoints?**

---

## 13. Scenario-Based Questions

86. **If the LLM is down, how does the system behave?**
87. **What happens if MongoDB is unavailable during upload?**
88. **How would you handle a corrupted PDF file?**
89. **What if the extracted data is completely wrong?**
90. **How would you implement a "re-process CV" feature?**

---

## 14. Future Enhancements

91. **How would you add multi-language CV support?**
92. **How would you implement CV comparison features?**
93. **What about skill matching with job descriptions?**
94. **How would you add user authentication and roles?**
95. **How would you implement batch CV upload?**

---

## 15. Behavioral/Situational

96. **What was the most challenging bug you encountered?**
97. **How did you approach learning the technologies used?**
98. **What would you do differently if starting over?**
99. **How did you decide on the tech stack?**
100. **How would you onboard a new developer to this project?**

---

*Last updated: February 1, 2026*
