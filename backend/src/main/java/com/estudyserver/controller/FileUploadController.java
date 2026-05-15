package com.estudyserver.controller;

import com.estudyserver.model.StudyQuestResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.client.RestTemplate;

import java.io.File;
import java.io.IOException;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api")
public class FileUploadController {

    // 自动读取 application.properties 里的上传路径
    @Value("${file.upload-path}")
    private String uploadDir;

    @PostMapping("/upload")
    public StudyQuestResponse uploadFile(@RequestParam("file") MultipartFile file) {
        StudyQuestResponse response = new StudyQuestResponse();

        if (file.isEmpty()) {
            response.setSuccess(false);
            response.setMessage("请选择一个文件上传！");
            return response;
        }

        try {
            //1.确保本地目录存在
            File directory = new File(uploadDir);
            if (!directory.exists()) {
                directory.mkdirs();
            }

            //2.生成防重名的新文件名
            String originalFilename = file.getOriginalFilename();
            String fileName = UUID.randomUUID().toString() + "_" + originalFilename;

            //3.构建完整的存储物理路径
            File dest = new File(directory.getAbsolutePath() + File.separator + fileName);

            //4.将文件保存到电脑的文件夹里
            file.transferTo(dest);
            String absoluteFilePath = dest.getAbsolutePath();

            // ==========================================
            //5.呼叫Agent
            // ==========================================
            RestTemplate restTemplate = new RestTemplate();
            String flaskUrl = "http://localhost:5000/api/studyquest";

            //构造要发给Flask的JSON参数
            Map<String, Object> requestToFlask = new HashMap<>();
            requestToFlask.put("request_type", "upload");
            requestToFlask.put("user_id", "user_001"); //先写死一个用户ID
            requestToFlask.put("file_paths", Collections.singletonList(absoluteFilePath)); // 把刚刚保存的图片绝对路径发过去

            //发起POST请求，呼叫AI。并把AI的结果返回给Android前端
            StudyQuestResponse flaskResponse = restTemplate.postForObject(flaskUrl, requestToFlask, StudyQuestResponse.class);
            return flaskResponse;

            //Mock
            /*
            StudyQuestResponse mockResponse = new StudyQuestResponse();
            mockResponse.setSuccess(true);
            mockResponse.setRequest_type("upload");
            mockResponse.setMessage("文件已保存本地，且[模拟AI]已处理完成！");

            Map<String, Object> fakeMaterial = new HashMap<>();
            fakeMaterial.put("material_id", "mat_mock_888");
            fakeMaterial.put("filename", originalFilename);
            fakeMaterial.put("file_type", "image");
            fakeMaterial.put("subject", "高等数学（AI模拟猜测）");
            fakeMaterial.put("knowledge_point", "多元函数偏导数");
            fakeMaterial.put("ocr_text_preview", "这是一段被模拟AI识别出来的公式文字...");

            Map<String, Object> fakeData = new HashMap<>();
            fakeData.put("file_path", absoluteFilePath);
            fakeData.put("materials", Collections.singletonList(fakeMaterial));
            fakeData.put("total_chunks", 1);
            fakeData.put("errors", Collections.emptyList());

            mockResponse.setData(fakeData);
            return mockResponse;
            */

        } catch (IOException e) {
            e.printStackTrace();
            response.setSuccess(false);
            response.setMessage("文件保存本地失败：" + e.getMessage());
            return response;
        } catch (Exception e) {
            e.printStackTrace();
            response.setSuccess(false);
            // 这里的报错通常是因为 Agent 队友的程序没启动，或者端口不对
            response.setMessage("呼叫AI失败，请检查Agent的Flask是否在localhost:5000启动：" + e.getMessage());
            return response;
        }
    }
}