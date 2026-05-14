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

    @GetMapping("/generate")
    public List<Task> generate(@RequestParam String goal) {
        //调用Flask接口
        RestTemplate rest = new RestTemplate();
        Map<String, String> body = new HashMap<>();
        body.put("goal", goal);

        //Flask跑在5000端口
        Map result = rest.postForObject("http://localhost:5000/api/planner", body, Map.class);

        //把AI的结果保存到数据库
        List<Map<String, Object>> stages = (List<Map<String, Object>>) result.get("stages");
        List<Task> savedTasks = new ArrayList<>();

        for (Map<String, Object> stage : stages) {
            Task t = new Task();
            //如果name为空则尝试读取 title
            String title = stage.containsKey("name") ? (String) stage.get("name") : (String) stage.get("title");
            t.setTitle(title);
            t.setContent((String) stage.get("desc"));
            t.setMinutes(30);
            savedTasks.add(taskRepository.save(t));
        }

        return savedTasks;
    }
}