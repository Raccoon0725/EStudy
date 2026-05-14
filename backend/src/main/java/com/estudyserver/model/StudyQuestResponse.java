package com.estudyserver.model;

import lombok.Data;

@Data
public class StudyQuestResponse {
    private boolean success;
    private String request_type; //plan,qa,upload,review,chat等
    private Object data;         //放具体的业务数据
    private String message;
    private String error;
}