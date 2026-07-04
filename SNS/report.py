"""集計結果と企画案をExcelファイルに出力する。"""
from openpyxl import Workbook


def create_report(summary, plan_ideas, output_path):
    """傾向データと投稿企画案をExcel1ファイル（2シート）にまとめて出力する。"""
    wb = Workbook()

    trend_sheet = wb.active
    trend_sheet.title = "傾向データ"
    trend_sheet.append(["集計投稿数", summary["video_count"]])
    trend_sheet.append([])
    trend_sheet.append(["人気ハッシュタグ", "件数"])
    for tag, count in summary["top_hashtags"]:
        trend_sheet.append([tag, count])

    trend_sheet.append([])
    trend_sheet.append(["いいね数上位の投稿", "いいね数", "URL"])
    for video in summary["top_videos_by_likes"]:
        trend_sheet.append([video["caption"], video["likes"], video["url"]])

    plan_sheet = wb.create_sheet("投稿企画案")
    plan_sheet.append(["企画案"])
    for idea in plan_ideas:
        plan_sheet.append([idea])

    wb.save(output_path)
