# classes.dex

.class public Lcom/nothing/NtFeaturesUtils;
.super Ljava/lang/Object;


# static fields
.field public static final FEATURE_GLYPH:I = 0x1

.field public static final FEATURE_NOTHING_STYLE:I = 0x2

.field public static final FEATURE_NT_CAMERA:I = 0x3


# direct methods
.method public constructor <init>()V
    .registers 1

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method

.method public static isSupport([I)Z
    .registers 2

    const/4 v0, 0x1

    return v0
.end method
