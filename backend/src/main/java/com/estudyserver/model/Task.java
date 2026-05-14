package com.estudyserver.model;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tasks")
public class Task {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "session_id")
    private String sessionId; //关联到上面的 Session

    private String title;

    @Column(columnDefinition = "TEXT")
    private String content;

    private Integer minutes;

    private String status = "pending";

    @Column(name = "created_at", insertable = false, updatable = false)
    private LocalDateTime createdAt;
}