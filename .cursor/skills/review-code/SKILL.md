---
name: review-code
description: Three-Critic Code Review Protocol
disable-model-invocation: true
---
# 🏛️ Three-Critic Code Review Protocol

## **OBJECTIVE**
Conduct a comprehensive, multi-perspective code review to identify and resolve all functional, performance, and quality issues.

---

## **PHASE 1: INDIVIDUAL REVIEWS**

### **🔍 CRITIC #1: FUNCTIONAL CORRECTNESS & ALGORITHM EXPERT**

**Your Focus Areas:**
1. **Functional Correctness**
   - Are all algorithms mathematically sound?
   - Are edge cases handled correctly?
   - Is the logic correct for all code paths?
   - Are there any off-by-one errors?
   - Is wraparound arithmetic handled correctly?

2. **State Management**
   - Are all state variables initialized properly?
   - Are state transitions handled correctly?
   - Are there any race conditions or inconsistent states?
   - Is shared state accessed safely?

3. **Counter & Timer Accuracy**
   - Are all counters updated correctly?
   - Do timers maintain long-term accuracy?
   - Is fractional tracking implemented correctly?
   - Are timer thresholds checked properly?

4. **Edge Cases & Corner Cases**
   - What happens at boundaries (0, max values)?
   - What happens during mode transitions?
   - What happens with timing jitter or delays?
   - What happens with unexpected call patterns?

**Review Template:**
```
✅ CORRECT: [List what works correctly]
⚠️ CONCERNS: [List potential issues or unclear areas]
❌ BUGS: [List definite bugs found]
💡 SUGGESTIONS: [List improvements]
```

---

### **🚀 CRITIC #2: PERFORMANCE & OPTIMIZATION EXPERT**

**Your Focus Areas:**
1. **Performance Optimization**
   - Are there unnecessary calculations?
   - Can any loops be optimized or eliminated?
   - Are expensive operations avoided in fast paths?
   - Is the code cache-friendly?
   - Are there redundant checks?

2. **Code Efficiency**
   - What is the cycle count for common paths?
   - Are there faster algorithms available?
   - Can branches be reordered for better prediction?
   - Are constants used effectively?

3. **Memory Efficiency**
   - Is memory usage minimized?
   - Are structures properly packed?
   - Are there memory leaks or dangling pointers?
   - Is stack usage reasonable?

4. **Fast Path Analysis**
   - Does the common case have minimal overhead?
   - Is the fast path truly fast?
   - Are slow operations deferred or avoided?

**Review Template:**
```
⚡ OPTIMIZED: [List efficient implementations]
🐌 SLOW PATHS: [List performance bottlenecks]
💾 MEMORY: [Memory usage analysis]
💡 OPTIMIZATIONS: [Suggested improvements]
```

---

### **📚 CRITIC #3: CODE QUALITY & MAINTAINABILITY EXPERT**

**Your Focus Areas:**
1. **Code Readability**
   - Is the code self-documenting?
   - Are variable names clear and descriptive?
   - Is the logic flow easy to follow?
   - Are complex sections explained?

2. **Standards Compliance**
   - Does it follow project coding standards?
   - Are naming conventions consistent?
   - Is documentation style appropriate?
   - Are comments concise and useful?

3. **Maintainability**
   - Will future developers understand this?
   - Is the code modular and testable?
   - Are magic numbers eliminated?
   - Are there duplicate code sections?

4. **Robustness**
   - Are assertions used appropriately?
   - Is error handling comprehensive?
   - Are assumptions documented?
   - Is the code defensive against misuse?

**Review Template:**
```
👍 GOOD PRACTICES: [List quality implementations]
📖 READABILITY: [Readability assessment]
🔧 MAINTENANCE: [Maintainability concerns]
💡 IMPROVEMENTS: [Suggested refinements]
```

---

## **PHASE 2: COLLABORATIVE DISCUSSION**

After individual reviews, all three critics discuss their findings together.

### **Discussion Protocol:**

**Step 1: Share Individual Findings**
- Each critic presents their findings
- No interruptions during presentations
- All findings are documented

**Step 2: Cross-Examination**
- Critics challenge each other's findings
- Debate significance and priority of issues
- Verify concerns through code analysis

**Step 3: Categorize Issues**
- **🔴 CRITICAL BUGS**: Must fix immediately (functional correctness, data corruption, crashes)
- **🟠 MAJOR ISSUES**: Should fix before release (performance problems, API issues)
- **🟡 MINOR ISSUES**: Nice to fix (code quality, minor optimizations)
- **🟢 ENHANCEMENTS**: Future improvements (optional optimizations, refactoring)

**Step 4: Prioritize Fixes**
- Rank issues by severity and impact
- Consider fix complexity vs. benefit
- Identify dependencies between fixes

**Step 5: Consensus Building**
- Agree on final assessment
- Document dissenting opinions if any
- Create actionable fix list

---

## **PHASE 3: CONSOLIDATED REPORT**

### **Format:**

```markdown
# 🏛️ THREE-CRITIC CODE REVIEW REPORT

## 📊 EXECUTIVE SUMMARY
- Overall Assessment: [APPROVED / NEEDS FIXES / MAJOR REWORK]
- Critical Issues Found: [Number]
- Major Issues Found: [Number]
- Minor Issues Found: [Number]

---

## 🔴 CRITICAL BUGS (Must Fix)

### Issue #1: [Title]
- **Severity**: CRITICAL
- **Found By**: Critic #[1/2/3]
- **Description**: [Detailed explanation]
- **Location**: [File:line]
- **Impact**: [What breaks]
- **Reproduction**: [How to trigger]
- **Suggested Fix**: [How to resolve]
- **Critics' Consensus**: [Unanimous/Majority/Split]

[Repeat for each critical bug]

---

## 🟠 MAJOR ISSUES (Should Fix)

### Issue #X: [Title]
[Same format as above]

---

## 🟡 MINOR ISSUES (Nice to Fix)

### Issue #X: [Title]
[Same format as above]

---

## 🟢 ENHANCEMENTS (Future Improvements)

### Enhancement #X: [Title]
[Same format as above]

---

## 💬 CRITICS' DISCUSSION HIGHLIGHTS

### Key Debates:
1. **[Topic]**: [Summary of discussion and resolution]
2. **[Topic]**: [Summary of discussion and resolution]

### Dissenting Opinions:
- **Critic #X on [Issue]**: [Minority opinion and reasoning]

---

## ✅ WHAT WORKS WELL

- [List of excellent implementations]
- [List of best practices observed]
- [List of clever solutions]

---

## 📋 RECOMMENDED ACTION PLAN

### Phase 1 (Immediate - Critical Bugs):
1. [ ] Fix issue #[X]: [Brief description]
2. [ ] Fix issue #[Y]: [Brief description]

### Phase 2 (Before Release - Major Issues):
1. [ ] Address issue #[X]: [Brief description]
2. [ ] Address issue #[Y]: [Brief description]

### Phase 3 (Post-Release - Minor Issues):
1. [ ] Improve [X]: [Brief description]

### Phase 4 (Future - Enhancements):
1. [ ] Consider [X]: [Brief description]

---

## 🎯 FINAL VERDICT

**Unanimous Consensus:**
- [ ] ✅ APPROVED - Production ready
- [ ] ⚠️ APPROVED WITH CONDITIONS - Fix critical bugs first
- [ ] ❌ NOT APPROVED - Major rework required

**Confidence Level**: [XX]%

**Signatures:**
- ✍️ Critic #1 (Functional): [APPROVE / CONDITIONAL / REJECT]
- ✍️ Critic #2 (Performance): [APPROVE / CONDITIONAL / REJECT]
- ✍️ Critic #3 (Quality): [APPROVE / CONDITIONAL / REJECT]
```

---

## **USAGE INSTRUCTIONS**

### **How to Use This Protocol:**

1. **Prepare the Code**
   - Identify the code section to review
   - Gather relevant context (requirements, design docs)
   - Note any specific concerns

2. **Execute Phase 1**
   - Have each critic independently review
   - No communication between critics during this phase
   - Each produces their individual review

3. **Execute Phase 2**
   - Bring critics together for discussion
   - Follow the discussion protocol
   - Document all debates and resolutions

4. **Execute Phase 3**
   - Compile the consolidated report
   - Ensure all issues are categorized
   - Create actionable fix list

5. **Review & Act**
   - Share report with development team
   - Prioritize and schedule fixes
   - Track resolution of issues

---

## **PROMPT TEMPLATE FOR AI CODE REVIEW**

### **Single Prompt Version (All-in-One):**

```
# THREE-CRITIC CODE REVIEW REQUEST

Please conduct a comprehensive code review using three expert critics:

## CRITICS:
1. **Critic #1**: Functional Correctness & Algorithm Expert
2. **Critic #2**: Performance & Optimization Expert  
3. **Critic #3**: Code Quality & Maintainability Expert

## PROTOCOL:

### PHASE 1: Individual Reviews
Each critic independently reviews the code from their expertise area.

**Critic #1 Focus**: Functional correctness, algorithms, state management, edge cases, timer accuracy
**Critic #2 Focus**: Performance, optimization, memory efficiency, fast path analysis
**Critic #3 Focus**: Code readability, standards compliance, maintainability, robustness

### PHASE 2: Collaborative Discussion
All three critics discuss their findings:
- Share individual findings
- Cross-examine concerns
- Debate significance and priority
- Categorize issues: CRITICAL / MAJOR / MINOR / ENHANCEMENT
- Build consensus

### PHASE 3: Consolidated Report
Produce a final report with:
- Executive summary
- All issues categorized by severity
- Critics' discussion highlights
- What works well
- Recommended action plan
- Final verdict with consensus

## CODE TO REVIEW:
[Insert code or file references here]

## SPECIFIC CONCERNS:
[Insert any specific areas of concern]

## REQUIREMENTS:
- Be brutally honest
- Find ALL bugs and issues
- Consider production readiness
- Provide actionable fixes
- Achieve critic consensus

Please proceed with the three-phase review.
```

---

## **EXAMPLES OF USE**

### **Example 1: Timer Implementation Review**

```
Using the Three-Critic Protocol, review the TCP ECO timer implementation in tcp.c:

Specific concerns:
- Timer accuracy over extended intervals (30 seconds)
- Counter updates during mode transitions
- Fast path performance overhead
- Edge cases with wraparound arithmetic

Focus on production readiness for commercial IoT devices.
```

### **Example 2: API Design Review**

```
Using the Three-Critic Protocol, review the new API additions:

Specific concerns:
- Thread safety
- API consistency with existing codebase
- Error handling completeness
- Documentation clarity

Focus on maintainability and developer experience.
```

### **Example 3: Optimization Review**

```
Using the Three-Critic Protocol, review the optimizations made to tcp_tmr():

Specific concerns:
- Does the fast path truly have zero overhead?
- Are all corner cases still handled correctly?
- Is long-term timer accuracy maintained?
- Are there any subtle functional regressions?

Focus on verifying that optimization didn't break functionality.
```

---

## **QUALITY METRICS**

A good review should:
- ✅ Find 100% of critical bugs
- ✅ Identify major performance bottlenecks
- ✅ Suggest concrete improvements
- ✅ Achieve critic consensus on severity
- ✅ Provide actionable fix recommendations
- ✅ Consider production readiness holistically

---

## **CERTIFICATION LEVELS**

Based on review results, code can be certified as:

| Level | Criteria | Suitable For |
|-------|----------|--------------|
| **Production Ready** | 0 critical bugs, <3 major issues | Commercial deployment |
| **Conditional Approval** | 0 critical bugs, 3-5 major issues | Deploy after fixes |
| **Major Rework Needed** | 1+ critical bugs, 5+ major issues | Not ready for production |
| **Safety-Critical Ready** | + Formal verification, certification | Medical, aviation, space |

---

## **NOTES**

- This protocol is designed for AI-assisted reviews but can be used with human reviewers
- Adjust focus areas based on project type (embedded, web, desktop, etc.)
- Scale critic count up or down based on complexity (3-5 critics recommended)
- Document all review findings for traceability
- Re-review after fixes are applied

---

**Version**: 1.0  
**Last Updated**: 2025-10-31  
**Maintained By**: Netstack Team
