# task 2 - how has the popularity of different music genres changed over time?
import time
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import matplotlib.pyplot as plt

spark = SparkSession.builder \
    .appName("GenrePopularityOverTime") \
    .getOrCreate()
 
# start overall timer 
start_time_task2 = time.time()
  
# remove all the other message beside the output 
spark.sparkContext.setLogLevel("WARN")

# uploading the dataset
df = spark.read.csv("/Users/emily/Desktop/cleaned_spotify_dataset_1.csv/updated_cleaned_dataset.csv",
    header = True,
    inferSchema = True)

#to found out the distinct genre type (explode each comma-separed genre)
one_genre = df.select(
	"*",
	F.explode(F.split(F.col("Genre"), ",")).alias("single_genre")
	).withColumn("single_genre", F.trim(F.col("single_genre")))  # remove white spaces
    
distinct_genres = one_genre.select("single_genre").distinct()
count = distinct_genres.count()
distinct_genres.show(count,truncate=False)
print(f"There are total of {count} different genres")
print() #newline

# add a new column call "year" of the Release Date
df = df.withColumn("year",F.year("Release Date"))

# Split comma-separated Genre strings and explode into one row per genre
genres = df.select(
    F.explode(F.split(F.col("Genre"), ",")).alias("genre"),
    F.col("Popularity").cast("double").alias("popularity")
).withColumn("genre", F.trim(F.col("genre")))

# Compute average popularity and count per genre
genre_stats = genres.groupBy("genre").agg(
    F.round(F.avg("popularity"), 2).alias("avg_popularity"),
    F.count("*").alias("track_count")
)

# filter out genres with very few tracks, e.g. fewer than 5
genre_stats = genre_stats.filter(F.col("track_count") >= 5)

# Order by descending average popularity and take top 10
top10 = genre_stats.orderBy(F.desc("avg_popularity")).limit(10)

# Show the results
print("\nTop 10 genres by average popularity:\n")
top10.show(truncate=False)

# convert to pandas for visulization 
plot1 = top10.toPandas().set_index("genre")
# Plot a bar chart
plt.figure()
plot1['avg_popularity'].plot(kind='bar')
plt.xlabel('Genre')
plt.ylabel('Average Popularity')
plt.title('Top 10 Genres by Average Popularity')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.show()
    
#find out the average popularity for each year and rank the genre for the top 10 highest avg_popularity
genre_by_year = df.select(
	"year",
	F.explode(F.split(F.col("Genre"),",")).alias("genre"),
	F.col("Popularity").cast("double").alias("popularity")
).withColumn("genre", F.trim(F.col("genre")))

year_genre_stats = (
    genre_by_year
        .groupBy("year", "Genre")
        .agg(
            F.round(F.avg("Popularity"), 2).alias("avg_popularity"),  
            F.count("*").alias("track_count")                         
             )  
    )

# filter out group that don't have much data (less than 5 tracks)
filtered_stats = year_genre_stats.filter(F.col("track_count") >= 5)

# rank the average popularity for each year 
w = Window.partitionBy("year").orderBy(F.desc("avg_popularity"))
ranked = filtered_stats.withColumn("rank", F.row_number().over(w))

#filter the top 5 most-common genres for each year 
top5_genres = ranked.filter(F.col("rank") <= 5)
    
table = top5_genres.select("year",
            "Genre",
            "avg_popularity",
            "track_count",
            "rank"
    )
    
# displaying the table 
table.orderBy("year", "rank").show(100, truncate=False)

#turn the top10 genre dataframe into a python list
top10_list = [row["genre"]for row in top10.select("genre").collect()]
yearly_top10=filtered_stats.filter(F.col("genre").isin(top10_list))

print("\nThe peak year for the top 10 genres have the highest average popularity:")
peaks_for_genre = (
    	yearly_top10
      		.groupBy("genre")
      		.agg(
       		   F.max(
         	   F.struct(
           	   F.col("avg_popularity"), 
           	   F.col("year")
          )
        ).alias("maxrec")
      )
      .select(
        "genre",
        F.col("maxrec.year").alias("peak_year"),
        F.col("maxrec.avg_popularity").alias("peak_popularity")
      )
   )
peaks_for_genre.show(truncate=False)

# bar plox
plot2 = peaks_for_genre.toPandas().set_index("genre")
plt.figure()
ax = plot2["peak_popularity"].plot(kind="bar", edgecolor="black")
plt.xlabel("Genre")
plt.ylabel("Peak Average Popularity")
plt.title("Top-10 Genres: Peak Year & Popularity")
plt.xticks(rotation=45, ha="right")

for i, (genre, row) in enumerate(plot2.iterrows()):
    	ax.text(
        	i, 
        	row["peak_popularity"] + 0.5,            
        	str(int(row["peak_year"])),      
        	ha="center", va="bottom"
    	)
plt.tight_layout()
plt.show()

# track the average popularity for each year
peaks_for_overall = (
    yearly_top10
        .withColumn("rank", F.row_number().over(w))
        .filter(F.col("rank") == 1)
        .select("genre","year","avg_popularity")
        .orderBy(F.desc("avg_popularity"))
    )
    
print("For each top-10 genre, the average popularity for each year:")
peaks_for_overall.show(truncate=False)

plot3 = yearly_top10.select("genre","year","avg_popularity").toPandas()   
pivot = plot3.pivot(index="year", columns="genre", values="avg_popularity").sort_index()

# line graph
plt.figure()
for genre in pivot.columns:
    plt.plot(pivot.index, pivot[genre], marker="o", label=genre)

plt.xlabel("Year")
plt.ylabel("Average Popularity")
plt.title("Popularity Over Time for Top-10 Genres")
plt.legend(loc="best", bbox_to_anchor=(1.02, 1))
plt.tight_layout()
plt.show()

print(f"Task 2 runtime: {time.time() - start_time_task2:.2f} seconds")
