package com.estudyserver.repository;

import com.estudyserver.model.QaLog;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QaLogRepository extends JpaRepository<QaLog, Long> {
}