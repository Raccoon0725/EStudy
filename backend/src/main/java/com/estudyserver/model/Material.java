package com.estudyserver.model;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "materials")
public class Material {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id")
    private Long userId;

    @Column(name = "filename")
    private String fileName;

    @Column(name = "file_path", length = 500)
    private String filePath; // 存在你电脑/服务器上的物理路径

    private String category; // 比如：高等数学/多元函数

    @Column(name = "uploaded_at", insertable = false, updatable = false)
    private LocalDateTime uploadAt;
}