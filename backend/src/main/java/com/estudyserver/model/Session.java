package com.estudyserver.model;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "sessions")
public class Session {
    @Id
    private String id; //这里的ID是Flask生成的字符串，所以不加自动递增

    @Column(name = "user_id")
    private Long userId;

    @Column(name = "goal_text", columnDefinition = "TEXT")
    private String goalText;

    @Column(name = "created_at", insertable = false, updatable = false)
    private LocalDateTime createdAt;
}