package com.estudyserver.model;

import lombok.Data;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

@Data
public class StudyQuestRequest {
    private String request_type; //plan,upload,qa,review,chat
    private String user_id;
    private String session_id;
    private String goal_text;
    private Double available_hours;
    private String question;

    //使用驼峰命名，但指定JSON字段名为answer_mode
    @JsonProperty("answer_mode")
    private String answerMode;

    private String active_task_id;
    //文档里的其他字段可根据需要添加，
}