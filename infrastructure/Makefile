.PHONY: build-CreateJobFunction build-ListJobsFunction build-GetJobFunction build-ConfirmUploadFunction
.PHONY: build-ProcessVideoFunction build-WsConnectFunction build-WsDisconnectFunction build-WsSubscribeFunction

SHARED_DIR := $(abspath ../backend/shared)
REQ_FILE := $(SHARED_DIR)/requirements.txt
FFMPEG_URL := https://github.com/ffbinaries/ffbinaries.com/raw/master/data/ffmpeg-static-linux-x64.zip
FFPROBE_URL := https://github.com/ffbinaries/ffbinaries.com/raw/master/data/ffprobe-static-linux-x64.zip

define build_lambda
	@echo "Building $(1)..."
	cp $(SHARED_DIR)/utils.py $(ARTIFACTS_DIR)/
	cp ../backend/upload-api/$(2)/handler.py $(ARTIFACTS_DIR)/
	python3 -m pip install -r $(REQ_FILE) -t $(ARTIFACTS_DIR)/ --quiet
endef

define build_shared_lambda
	@echo "Building $(1)..."
	cp $(SHARED_DIR)/utils.py $(ARTIFACTS_DIR)/
	cp ../backend/$(2)/handler.py $(ARTIFACTS_DIR)/
	python3 -m pip install -r $(REQ_FILE) -t $(ARTIFACTS_DIR)/ --quiet
endef

build-CreateJobFunction:
	$(call build_lambda,CreateJobFunction,create_job)

build-ListJobsFunction:
	$(call build_lambda,ListJobsFunction,list_jobs)

build-GetJobFunction:
	$(call build_lambda,GetJobFunction,get_job)

build-ConfirmUploadFunction:
	$(call build_lambda,ConfirmUploadFunction,confirm_upload)

build-ProcessVideoFunction:
	@echo "Building ProcessVideoFunction..."
	cp $(SHARED_DIR)/utils.py $(ARTIFACTS_DIR)/
	cp $(SHARED_DIR)/video_processor.py $(ARTIFACTS_DIR)/
	cp ../backend/processing/process_video/handler.py $(ARTIFACTS_DIR)/
	python3 -m pip install -r $(REQ_FILE) -t $(ARTIFACTS_DIR)/ --quiet
	curl -sL $(FFMPEG_URL) -o /tmp/vf-ffmpeg.zip
	curl -sL $(FFPROBE_URL) -o /tmp/vf-ffprobe.zip
	unzip -o -j /tmp/vf-ffmpeg.zip ffmpeg -d $(ARTIFACTS_DIR)/
	unzip -o -j /tmp/vf-ffprobe.zip ffprobe -d $(ARTIFACTS_DIR)/
	chmod +x $(ARTIFACTS_DIR)/ffmpeg $(ARTIFACTS_DIR)/ffprobe

build-WsConnectFunction:
	$(call build_shared_lambda,WsConnectFunction,websocket/connect)

build-WsDisconnectFunction:
	$(call build_shared_lambda,WsDisconnectFunction,websocket/disconnect)

build-WsSubscribeFunction:
	$(call build_shared_lambda,WsSubscribeFunction,websocket/subscribe)
