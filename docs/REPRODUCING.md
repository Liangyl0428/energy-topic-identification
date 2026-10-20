# 复现与运行

当前全量入口可读取本仓库的 `config/runtime_paths.json`；跨模块 P1/P2 构建使用组装后的 `final` 运行包。先参照 [平台接入说明](PLATFORM_INTEGRATION.md) 确认运行布局。先查看[运行配置与输入清单](https://github.com/Liangyl0428/energy-topic-identification/blob/main/platform/docs/运行配置与输入清单.md)和[平台字段字典](https://github.com/Liangyl0428/energy-topic-identification/blob/main/platform/docs/数据与指标字典.md)。数据根目录、冻结语料、元数据库、BGE 模型和输出位置均可配置；相对路径相对于配置文件，不依赖启动目录。

在项目根目录先做只读预检：

```sh
.venv-hotspots/bin/python final/tools/check_inputs.py
```

外部语料、模型和元数据库不会随紧凑交付打包。搬迁时保留 `final/runtime_config.py` 与 `final/config/`，设置 `ENERGY_DATA_ROOT` 或 `ENERGY_PLATFORM_CONFIG`；缺失依赖会明确报错。基础依赖见本模块 requirements 或 pyproject。

## 分类全量流程

```sh
.venv-hotspots/bin/python final/energy-topic-identification/pipelines/full_nmf/status.py
.venv-hotspots/bin/python final/energy-topic-identification/pipelines/full_nmf/run.py
```

默认配置引用已有完成缓存；独立重跑前把 `classification_run` 或 `FULL_NMF_RUN` 指向新目录。流程按 prepare、encode、train、finalize、下游 build 和本地资产导出执行。不要在同一缓存目录并发启动。编码仍需既有 Python 3.10、ONNX CUDA 运行时和 BGE-M3 权重。

输入关键词清单含绝对路径，按统一配置 `source_path_prefixes` 重定位。模型、向量和逐条分配留在配置的工作目录；加载 NMF 需要把 `pipelines/full_nmf` 加入模块路径并导入对应模型类。

P0 没有重跑分类，也没有修改主题成员或模型权重。历史发布调度脚本不属于本地复现入口，未在本次执行。

## 本地校验

在模块目录按 README 的 CPU 测试命令运行；可选 ONNX 和 BERTopic 兼容测试需另装其依赖。发布前需更新本地资产和源码指纹；当前 P0 的统一验收结果见[验收记录](https://github.com/Liangyl0428/energy-topic-identification/blob/main/platform/docs/P0修复验收.md)。完整性检查通过只说明字段、证据及版本一致，不替代主题语义审核或正式成熟度评定。
