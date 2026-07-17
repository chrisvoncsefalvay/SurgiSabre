/*
 * ARM64 compatibility shim for Isaac Sim 6.0.1 and pinned IsaacTeleop.
 *
 * NVIDIA does not publish isaacsim.kit.xr.teleop.bridge for linux-aarch64.
 * That bridge normally contributes DeviceIO's required extensions before Kit
 * calls xrCreateInstance. Interpose only the named Isaac Lab application and
 * append the four extensions used by the controller and teleop pipelines.
 */

#define _GNU_SOURCE

#include <dlfcn.h>
#include <openxr/openxr.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *const k_required_extensions[] = {
    "XR_KHR_convert_timespec_time",
    "XR_NVX1_action_context",
    "XR_NV_opaque_data_channel",
    "XR_NVX1_tensor_data",
};

static bool contains_extension(const XrInstanceCreateInfo *create_info, const char *extension) {
    for (uint32_t index = 0; index < create_info->enabledExtensionCount; ++index) {
        if (strcmp(create_info->enabledExtensionNames[index], extension) == 0) {
            return true;
        }
    }
    return false;
}

XRAPI_ATTR XrResult XRAPI_CALL xrCreateInstance(
    const XrInstanceCreateInfo *create_info,
    XrInstance *instance) {
    static PFN_xrCreateInstance real_xr_create_instance = NULL;
    static void *openxr_loader_handle = NULL;
    if (real_xr_create_instance == NULL) {
        *(void **)(&real_xr_create_instance) = dlsym(RTLD_NEXT, "xrCreateInstance");
        if (real_xr_create_instance == NULL) {
            const char *loader_path = getenv("ISAAC_TELEOP_OPENXR_LOADER");
            if (loader_path != NULL && loader_path[0] != '\0') {
                openxr_loader_handle = dlopen(loader_path, RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD);
                if (openxr_loader_handle != NULL) {
                    *(void **)(&real_xr_create_instance) = dlsym(openxr_loader_handle, "xrCreateInstance");
                }
            }
            if (real_xr_create_instance == NULL) {
                fprintf(
                    stderr,
                    "[surgisabre-openxr] could not resolve xrCreateInstance from Kit loader: %s\n",
                    dlerror());
                return XR_ERROR_RUNTIME_FAILURE;
            }
        }
    }

    const char *target_app = getenv("ISAAC_TELEOP_OPENXR_INJECT_APP");
    if (create_info == NULL ||
        (create_info->enabledExtensionCount != 0 && create_info->enabledExtensionNames == NULL) ||
        target_app == NULL || target_app[0] == '\0' ||
        strcmp(create_info->applicationInfo.applicationName, target_app) != 0) {
        return real_xr_create_instance(create_info, instance);
    }

    const size_t required_count = sizeof(k_required_extensions) / sizeof(k_required_extensions[0]);
    if (create_info->enabledExtensionCount > UINT32_MAX - required_count) {
        return XR_ERROR_LIMIT_REACHED;
    }
    const size_t capacity = (size_t)create_info->enabledExtensionCount + required_count;
    const char **enabled_extensions = calloc(capacity, sizeof(*enabled_extensions));
    if (enabled_extensions == NULL) {
        return XR_ERROR_OUT_OF_MEMORY;
    }

    size_t enabled_count = create_info->enabledExtensionCount;
    for (size_t index = 0; index < enabled_count; ++index) {
        enabled_extensions[index] = create_info->enabledExtensionNames[index];
    }

    fprintf(stderr, "[surgisabre-openxr] injecting required extensions for application %s:", target_app);
    for (size_t index = 0; index < required_count; ++index) {
        const char *extension = k_required_extensions[index];
        if (!contains_extension(create_info, extension)) {
            enabled_extensions[enabled_count++] = extension;
            fprintf(stderr, " %s", extension);
        }
    }
    fputc('\n', stderr);

    XrInstanceCreateInfo patched_create_info = *create_info;
    patched_create_info.enabledExtensionCount = (uint32_t)enabled_count;
    patched_create_info.enabledExtensionNames = enabled_extensions;
    const XrResult result = real_xr_create_instance(&patched_create_info, instance);
    free(enabled_extensions);
    return result;
}
