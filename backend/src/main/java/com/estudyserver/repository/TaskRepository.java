package com.estudyserver.repository;

import com.estudyserver.model.Task;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface TaskRepository extends JpaRepository<Task, Long> {

    //JPA会自动根据方法名生成对应的SQL：SELECT * FROM tasks WHERE session_id = ?
    List<Task> findBySessionId(String sessionId);
}