package com.estudyserver.controller;

import com.estudyserver.repository.TaskRepository;
import com.estudyserver.model.Task;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import java.util.*;

@RestController
@RequestMapping("/api/tasks")
@CrossOrigin(origins = "*")     //加跨域，方便Android同学
public class TaskController {

    @Autowired
    private TaskRepository taskRepository;

    /**
     *功能1.获取某个学习会话下的所有关卡任务清单
     *Android端拿到SessionId后，直接调用此接口渲染关卡列表树
     */
    @GetMapping("/session/{sessionId}")
    public List<Task> getTasksBySession(@PathVariable String sessionId) {
        return taskRepository.findBySessionId(sessionId);
    }

    /**
     *功能2.更新指定关卡的状态（关卡进行中 /关卡打卡完成）
     *对应组件打卡逻辑，更新成功后可触发Python端的Review统计
     */
    @PutMapping("/{id}/status")
    public Map<String, Object> updateTaskStatus(
            @PathVariable Long id,
            @RequestParam String status) {

        Map<String, Object> response = new HashMap<>();
        Optional<Task> taskOptional = taskRepository.findById(id);

        if (taskOptional.isPresent()) {
            Task task = taskOptional.get();
            task.setStatus(status); //更新为 "in_progress" 或 "completed"
            taskRepository.save(task);

            response.put("success", true);
            response.put("message", "关卡状态成功更新为: " + status);
            response.put("data", task);
        } else {
            response.put("success", false);
            response.put("message", "未找到指定关卡，ID: " + id);
        }

        return response;
    }

    /* =========================================================================
       历史遗留接口说明：
       下面的generate接口属于系统早期MVP阶段的直连测试代码。
       目前系统的规划功能已经完全统一收口到 /api/studyquest (request_type="plan") 中。
       这里做针对性重构，修复了字段断层，仅保留作为后备测试端点。
       ========================================================================= */
    @GetMapping("/generate")
    public List<Task> generate(@RequestParam String goal) {
        try {
            RestTemplate rest = new RestTemplate();
            Map<String, String> body = new HashMap<>();
            body.put("goal", goal);

            //若Python端废弃了旧的 /api/planner 路由，此接口调用会报404
            Map result = rest.postForObject("http://localhost:5000/api/planner", body, Map.class);
            List<Task> savedTasks = new ArrayList<>();

            if (result != null && result.get("tasks") != null) {
                List<Map<String, Object>> tasks = (List<Map<String, Object>>) result.get("tasks");

                //为独立测试临时生成一个虚拟的session_id，保证不触发外键冲突
                String mockSessionId = "sess_mock_" + UUID.randomUUID().toString().substring(0, 6);

                for (Map<String, Object> taskMap : tasks) {
                    Task t = new Task();
                    t.setSessionId(mockSessionId);
                    t.setTitle((String) taskMap.get("title"));
                    t.setContent((String) taskMap.get("description"));
                    //动态读取大模型给出的建议时长
                    Integer mins = (Integer) taskMap.get("estimated_minutes");
                    t.setMinutes(mins != null ? mins : 30);
                    t.setStatus("pending");
                    savedTasks.add(taskRepository.save(t));
                }
            }
            return savedTasks;
        } catch (Exception e) {
            e.printStackTrace();
            return new ArrayList<>(); //异常防御返回空列表
        }
    }
}