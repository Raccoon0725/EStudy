package com.estudyserver.controller;

import com.estudyserver.model.StudyQuestResponse;
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

    //为了测试方便就在本地文件夹了，请手动在D盘创建uploads文件夹，不然这个功能会报错
    private static final String UPLOAD_DIR = "D:/uploads/";

    @PostMapping("/upload")
    public StudyQuestResponse uploadFile(@RequestParam("file") MultipartFile file) {
        StudyQuestResponse response = new StudyQuestResponse();

        if (file.isEmpty()) {
            response.setSuccess(false);
            response.setMessage("请选择一个文件上传！");
            return response;
        }

        try {
            //1.确保目录存在
            File dir = new File(UPLOAD_DIR);
            if (!dir.exists()) {
                dir.mkdirs();
            }

            //2.生成唯一文件名
            String originalFilename = file.getOriginalFilename();
            String newFileName = UUID.randomUUID().toString() + "_" + originalFilename;
            String filePath = UPLOAD_DIR + newFileName;

            //3.保存文件到本地D盘
            File dest = new File(filePath);
            file.transferTo(dest);

            //预留的Flask调用
            //RestTemplate restTemplate = new RestTemplate();
            //String flaskUrl = "http://localhost:5000/api/studyquest"; //文档中的统一接口

            //文档2.3节构造请求参数
            //Map<String, Object> requestToFlask = new HashMap<>();
            //requestToFlask.put("request_type", "upload");
            //requestToFlask.put("user_id", "user_001"); //暂时写死一个测试用户ID
            //requestToFlask.put("file_paths", Collections.singletonList(filePath)); //传绝对路径给Flask

            //发起调用
            //StudyQuestResponse flaskResponse = restTemplate.postForObject(flaskUrl, requestToFlask, StudyQuestResponse.class);

            //直接把Flask处理完的结果返回给前端
            //return flaskResponse;

            //=======以下进行测试=================
            StudyQuestResponse mockResponse = new StudyQuestResponse();
            mockResponse.setSuccess(true);
            mockResponse.setRequest_type("upload");
            mockResponse.setMessage("文件已保存到D盘，且[模拟AI]已处理完成！");

            //伪造一下信息
            Map<String, Object> fakeMaterial = new HashMap<>();
            fakeMaterial.put("material_id", "mat_mock_888"); //假的资料ID
            fakeMaterial.put("filename", originalFilename);
            fakeMaterial.put("file_type", "image");
            fakeMaterial.put("subject", "高等数学（AI模拟猜测）");
            fakeMaterial.put("knowledge_point", "多元函数偏导数");
            fakeMaterial.put("ocr_text_preview", "这是一段被模拟AI识别出来的公式文字...");

            //资料放进data里
            Map<String, Object> fakeData = new HashMap<>();
            fakeData.put("materials", Collections.singletonList(fakeMaterial));
            fakeData.put("total_chunks", 1);
            fakeData.put("errors", Collections.emptyList());

            mockResponse.setData(fakeData);

            return mockResponse;

        } catch (IOException e) {
            e.printStackTrace();
            response.setSuccess(false);
            response.setMessage("文件保存失败：" + e.getMessage());
            return response;
        } catch (Exception e) {
            e.printStackTrace();
            response.setSuccess(false);
            response.setMessage("呼叫AI处理失败，请检查Flask是否启动：" + e.getMessage());
            return response;
        }
    }
}