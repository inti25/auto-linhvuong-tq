namespace LVClient
{
	partial class frmThongBaoDanhTuongViengTham
	{
		/// <summary>
		/// Required designer variable.
		/// </summary>
		private System.ComponentModel.IContainer components = null;

		/// <summary>
		/// Clean up any resources being used.
		/// </summary>
		/// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
		protected override void Dispose(bool disposing)
		{
			if (disposing && (components != null))
			{
				components.Dispose();
			}
			base.Dispose(disposing);
		}

		#region Windows Form Designer generated code

		/// <summary>
		/// Required method for Designer support - do not modify
		/// the contents of this method with the code editor.
		/// </summary>
		private void InitializeComponent()
		{
			this.lblAlertCoDanhTuong = new System.Windows.Forms.Label();
			this.SuspendLayout();
			// 
			// lblAlertCoDanhTuong
			// 
			this.lblAlertCoDanhTuong.AutoSize = true;
			this.lblAlertCoDanhTuong.Location = new System.Drawing.Point(0, 8);
			this.lblAlertCoDanhTuong.Name = "lblAlertCoDanhTuong";
			this.lblAlertCoDanhTuong.Size = new System.Drawing.Size(35, 13);
			this.lblAlertCoDanhTuong.TabIndex = 0;
			this.lblAlertCoDanhTuong.Text = "label1";
			// 
			// frmThongBaoDanhTuongViengTham
			// 
			this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
			this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
			this.ClientSize = new System.Drawing.Size(352, 74);
			this.Controls.Add(this.lblAlertCoDanhTuong);
			this.Name = "frmThongBaoDanhTuongViengTham";
			this.Text = "Xuân vãi, có danh tướng ghé qua nè";
			this.ResumeLayout(false);
			this.PerformLayout();

		}

		#endregion

		public System.Windows.Forms.Label lblAlertCoDanhTuong;

	}
}