package com.estudyserver.controller;

import com.estudyserver.model.*;
import com.estudyserver.repository.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.*;

@RestController
@RequestMapping("/api")
public class StudyQuestController {

    @Autowired
    private SessionRepository sessionRepository;

    @Autowired
    private TaskRepository taskRepository;

    //注入答疑日志仓库
    @Autowired
    private QaLogRepository qaLogRepository;

    @PostMapping("/studyquest")
    public StudyQuestResponse handleRequest(@RequestBody StudyQuestRequest request) {

        //真实代码
        try {
            //呼叫Flask端的Agent
            RestTemplate restTemplate = new RestTemplate();
            String flaskUrl = "http://localhost:5000/api/studyquest";

            //发起请求并接收Flask的回应
            StudyQuestResponse flaskResponse = restTemplate.postForObject(flaskUrl, request, StudyQuestResponse.class);

            //如果Agent成功规划了关卡，把它存入MySQL
            if (flaskResponse != null && flaskResponse.isSuccess()) {
                Map<String, Object> data = (Map<String, Object>) flaskResponse.getData();

                if (data == null) {
                    flaskResponse.setSuccess(false);
                    flaskResponse.setMessage("AI助手未能在资料库中找到相关内容，请尝试重新上传或更换提问方式");
                    return flaskResponse; //提前返回，不再往下走逻辑
                }

                String rt = flaskResponse.getRequest_type();

                if ("plan".equals(rt)) {
                    //(1)提取并保存Session
                    String sessionId = (String) data.get("session_id");
                    Session session = new Session();
                    session.setId(sessionId);

                    //去掉了 Long.valueOf()，直接传 String
                    session.setUserId(request.getUser_id());
                    session.setGoalText(request.getGoal_text());
                    sessionRepository.save(session);

                    //(2)提取并保存Tasks列表
                    List<Map<String, Object>> tasks = (List<Map<String, Object>>) data.get("tasks");
                    if (tasks != null) {
                        for (Map<String, Object> taskMap : tasks) {
                            Task t = new Task();
                            t.setSessionId(sessionId);
                            t.setTitle((String) taskMap.get("title"));
                            //按照队友文档，任务描述字段叫description
                            t.setContent((String) taskMap.get("description"));
                            t.setMinutes((Integer) taskMap.get("estimated_minutes"));
                            t.setStatus("pending");
                            taskRepository.save(t);
                        }
                    }
                }
                //如果是答疑请求，把回答存入qa_logs
                else if ("qa".equals(rt)) {
                    QaLog log = new QaLog();
                    //去掉了 Long.valueOf()，直接传 String
                    log.setUserId(request.getUser_id());
                    log.setQuestion(request.getQuestion());
                    log.setAnswer((String) data.get("answer"));
                    log.setMode((String) data.get("answer_mode"));
                    qaLogRepository.save(log);
                }
            }

            //把Flask处理完的结果，原样返回给Android前端
            return flaskResponse;

        } catch (Exception e) {
            e.printStackTrace();
            StudyQuestResponse errorResponse = new StudyQuestResponse();
            errorResponse.setSuccess(false);
            errorResponse.setMessage("呼叫Flask Agent失败，请检查Python服务是否启动: " + e.getMessage());
            return errorResponse;
        }
    }

    /* =========================================================
       下面是测试用的 Mock 代码，现已全部封印在注释中
       ========================================================= */
    /*
    //测试
    String type = request.getRequest_type();
    if ("plan".equals(type)) {
        return mockPlanResponse(request);
    } else if ("chat".equals(type)) {
        return mockChatResponse(request);
    } else if ("qa".equals(type)) {
        return mockQaResponse(request);
    } else if ("review".equals(type)) {
        return mockReviewResponse(request);
    }

    StudyQuestResponse response = new StudyQuestResponse();
    response.setSuccess(false);
    response.setMessage("暂不支持的请求类型: " + type);
    return response;

    //Mock
    private StudyQuestResponse mockPlanResponse(StudyQuestRequest req) {
        String newSessionId = "sess_" + UUID.randomUUID().toString().substring(0, 8);

        Session session = new Session();
        session.setId(newSessionId);
        session.setGoalText(req.getGoal_text());
        //这里暂时写死为1L，为了迎合目前数据库里的假用户
        session.setUserId(1L);
        sessionRepository.save(session);

        List<Map<String, Object>> tasksList = new ArrayList<>();
        for (int i = 1; i <= 2; i++) {
            Task t = new Task();
            t.setSessionId(newSessionId);
            t.setTitle(i == 1 ? "基础概念梳理" : "核心例题精讲");
            t.setContent("这是针对 [" + req.getGoal_text() + "] 的模拟任务内容");
            t.setMinutes(30);
            taskRepository.save(t);

            Map<String, Object> taskMap = new HashMap<>();
            taskMap.put("title", t.getTitle());
            taskMap.put("estimated_minutes", t.getMinutes());
            tasksList.add(taskMap);
        }

        StudyQuestResponse res = new StudyQuestResponse();
        res.setSuccess(true);
        res.setRequest_type("plan");
        res.setMessage("学习关卡规划完成（模拟数据已存入数据库）");

        Map<String, Object> data = new HashMap<>();
        data.put("session_id", newSessionId);
        data.put("tasks", tasksList);
        res.setData(data);

        return res;
    }

    private StudyQuestResponse mockChatResponse(StudyQuestRequest req) {
        StudyQuestResponse res = new StudyQuestResponse();
        res.setSuccess(true);
        res.setRequest_type("qa");
        res.setMessage("答疑完成");

        Map<String, Object> data = new HashMap<>();
        data.put("answer", "你刚才说的是：'" + req.getGoal_text() + "'。作为AI助手，我建议你先从基础看起。");
        res.setData(data);
        return res;
    }

    //Mock Qa
    private StudyQuestResponse mockQaResponse(StudyQuestRequest req) {
        QaLog log = new QaLog();
        log.setUserId(1L);
        log.setQuestion(req.getQuestion() != null ? req.getQuestion() : "模拟提问内容");
        log.setAnswer("## 模拟解答\n这里是 AI 针对问题的详细分析。");
        //log.setMode(req.getAnswer_mode() != null ? req.getAnswer_mode() : "explain");
        log.setMode(req.getAnswerMode() != null ? req.getAnswerMode() : "explain");
        qaLogRepository.save(log);

        StudyQuestResponse res = new StudyQuestResponse();
        res.setSuccess(true);
        res.setRequest_type("qa");
        res.setMessage("答疑完成（模拟数据）");

        Map<String, Object> data = new HashMap<>();
        data.put("answer", log.getAnswer());
        data.put("qa_log_id", "qa_" + log.getId());
        res.setData(data);
        return res;
    }

    //Mock Review
    private StudyQuestResponse mockReviewResponse(StudyQuestRequest req) {
        StudyQuestResponse res = new StudyQuestResponse();
        res.setSuccess(true);
        res.setRequest_type("review");
        res.setMessage("学习报告已生成（模拟数据）");

        Map<String, Object> data = new HashMap<>();
        data.put("report_id", "rpt_" + UUID.randomUUID().toString().substring(0, 6));
        data.put("next_tasks_suggestion", "建议明天重点复习多元函数全微分。");
        res.setData(data);
        return res;
    }
    */
}